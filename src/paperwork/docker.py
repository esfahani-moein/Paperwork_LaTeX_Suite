"""Manage the shared compile container and execute TeX commands in it."""

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep

import click

_START_TIMEOUT = 30
_WAIT = ("--wait", "--wait-timeout", str(_START_TIMEOUT))


@dataclass(frozen=True)
class _Container:
    status: str
    health: str | None
    image_id: str
    network_mode: str

    @property
    def ready(self) -> bool:
        return self.status == "running" and self.health in (None, "healthy")


class Docker:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.name = os.environ.get("PAPER_CONTAINER_NAME") or "paper-latex"
        self.image_id = ""
        self.network_mode = ""
        self._env = {**os.environ, "PAPER_ROOT": str(self.root)}
        self._compose_args = (
            "compose",
            "--project-directory",
            str(self.root),
            "--file",
            str(self.root / "compose.yaml"),
            "--env-file",
            str(self.root / "paper.env"),
        )

    def _docker(
        self, args: Sequence[str], *, check: bool = True, capture_output: bool = False
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ("docker", *args),
                env=self._env,
                check=check,
                capture_output=capture_output,
                text=True,
            )
        except FileNotFoundError:
            raise click.ClickException(
                "Docker CLI is missing. Make Docker available on PATH."
            ) from None
        except subprocess.CalledProcessError as error:
            if error.stderr:
                raise click.ClickException(error.stderr.strip()) from None
            raise

    def _compose(
        self, *args: str, capture_output: bool = False
    ) -> subprocess.CompletedProcess[str]:
        return self._docker((*self._compose_args, *args), capture_output=capture_output)

    def _daemon_version(self) -> str:
        result = self._docker(
            ("version", "--format", "{{.Server.Version}}"),
            check=False,
            capture_output=True,
        )
        if result.returncode:
            detail = result.stderr.strip()
            raise click.ClickException(
                f"Docker daemon is unavailable. Start your Docker runtime. {detail}".strip()
            )
        return result.stdout.strip()

    def _container(self) -> _Container | None:
        result = self._docker(
            ("container", "inspect", "--format", "{{json .}}", "--", self.name),
            check=False,
            capture_output=True,
        )
        if result.returncode:
            detail = result.stderr.strip()
            if (
                "no such container" in detail.lower()
                or "no such object" in detail.lower()
            ):
                return None
            self._daemon_version()
            raise click.ClickException(
                f"Cannot inspect container {self.name!r}. {detail}".strip()
            )

        record = json.loads(result.stdout)
        labels = record["Config"]["Labels"] or {}
        if labels.get("com.docker.compose.service") != "paper" or labels.get(
            "com.docker.compose.project.working_dir"
        ) != str(self.root):
            raise click.ClickException(
                f"Container {self.name!r} belongs to a different service or Paper Suite checkout."
            )
        state = record["State"]
        return _Container(
            state["Status"],
            (state.get("Health") or {}).get("Status"),
            record["Image"],
            record["HostConfig"]["NetworkMode"],
        )

    def _image(self) -> str:
        return self._compose(
            "config", "--images", "paper", capture_output=True
        ).stdout.strip()

    def _image_exists(self, image: str) -> bool:
        result = self._docker(
            ("image", "inspect", "--", image), check=False, capture_output=True
        )
        if result.returncode == 0:
            return True
        detail = result.stderr.strip()
        if "no such image" in detail.lower() or "no such object" in detail.lower():
            return False
        self._daemon_version()
        raise click.ClickException(f"Cannot inspect image {image!r}. {detail}".strip())

    def ready(self) -> None:
        """Check the running service or request approval to start it."""
        container = self._container()
        if container is None:
            image = self._image()
            if self._image_exists(image):
                _confirm(
                    f"Start the shared compiler using {image}?",
                    "Compiler is stopped. Run `paper up`.",
                )
                self._start("--no-recreate")
            else:
                _confirm(
                    f"Build the missing image {image} and start the shared compiler?",
                    f"Image {image} is missing. Run `paper up --build`.",
                )
                self.up(build=True)
            container = self._container()
        elif container.status in ("created", "exited"):
            _confirm(
                "Start the shared compiler?", "Compiler is stopped. Run `paper up`."
            )
            self._compose("start", *_WAIT, "paper")
            container = self._container()

        if (
            container is not None
            and container.status == "running"
            and container.health == "starting"
        ):
            deadline = monotonic() + _START_TIMEOUT
            while (
                container is not None
                and container.status == "running"
                and container.health == "starting"
                and monotonic() < deadline
            ):
                sleep(0.5)
                container = self._container()
        if container is None or not container.ready:
            raise _not_ready(self.name, container)
        self.image_id = container.image_id
        self.network_mode = container.network_mode

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Execute in the shared container after the caller checks readiness."""
        command = ["exec", "-i"]
        if cwd is not None:
            command.extend(("--workdir", str(cwd)))
        command.extend(("--", self.name, *args))
        return self._docker(command, check=check, capture_output=capture_output)

    def _start(self, *args: str) -> None:
        self._compose("up", "--no-build", "--pull", "never", *_WAIT, *args, "paper")

    def up(self, *, build: bool = False) -> None:
        if not build:
            image = self._image()
            if not self._image_exists(image):
                _confirm(
                    f"Build the missing image {image} and start the shared compiler?",
                    f"Image {image} is missing. Run `paper up --build`.",
                )
                build = True
        if build:
            self._compose("build", "paper")
        self._start()

    def down(self) -> None:
        self._compose("down")

    def rebuild(self) -> None:
        self._env["BUILD_ID"] = self._env.get("BUILD_ID") or datetime.now(UTC).strftime(
            "%Y%m%d%H%M%S"
        )
        self._compose("build", "--pull", "--no-cache", "paper")
        self._start("--force-recreate")

    def doctor(self) -> None:
        click.echo(f"Docker daemon {self._daemon_version()}")
        image = self._image()
        available = self._image_exists(image)
        click.echo(f"Image {image} ({'available' if available else 'missing'})")
        container = self._container()
        if container is None or not container.ready:
            if not available and container is None:
                raise click.ClickException(
                    f"Image {image} is missing. Run `paper up --build`."
                )
            raise _not_ready(self.name, container)
        click.echo(
            f"Container {self.name} ({container.health or 'running'}, {container.image_id})"
        )
        self.run(("test", "-w", "/build"))
        self.run(("latexmk", "-version"))
        self.run(("pdflatex", "--version"))
        self.run(("tectonic", "--version"))
        self.run(("texpresso", "-capabilities"), capture_output=True)


def _confirm(prompt: str, diagnosis: str) -> None:
    if (
        sys.stdin.isatty()
        and sys.stderr.isatty()
        and click.confirm(prompt, default=False, err=True)
    ):
        return
    raise click.ClickException(diagnosis)


def _not_ready(name: str, container: _Container | None) -> click.ClickException:
    if container is None:
        return click.ClickException(f"Container {name!r} is missing. Run `paper up`.")
    if container.status in ("created", "exited"):
        return click.ClickException(f"Container {name!r} is stopped. Run `paper up`.")
    state = (
        container.health
        if container.status == "running" and container.health
        else container.status
    )
    return click.ClickException(
        f"Container {name!r} is {state}. Check `docker inspect {name}`."
    )
