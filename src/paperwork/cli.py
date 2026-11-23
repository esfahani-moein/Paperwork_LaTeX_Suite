"""The installed ``paper`` command and the checkout entry point."""

import os
import subprocess
from pathlib import Path

import click

from .build import build, project_lock, publish_file
from .docker import Docker
from .project import (
    CACHE_DIR,
    ProjectError,
    load_project,
    new_project,
    project_root,
)
from .staging import StagingError, stage_project, sync_synctex


def _docker() -> Docker:
    checkout = Path(
        os.environ.get("PAPERSUITE_HOME", Path(__file__).resolve().parents[2])
    )
    if not (checkout / "compose.yaml").is_file():
        raise click.ClickException(
            "Set PAPERSUITE_HOME to the Paperwork deployment checkout."
        )
    return Docker(checkout)


@click.group()
def cli() -> None:
    """Create LaTeX projects and compile them in the shared Docker service."""


@cli.command()
@click.argument("name")
@click.option("--template", default="article", show_default=True)
def new(name: str, template: str) -> None:
    """Create a Git-backed paper in the current directory."""
    click.echo(f"Created {new_project(name, template, cwd=Path.cwd())}")


@cli.command("build")
@click.argument("source", type=click.Path(path_type=Path), required=False)
@click.option(
    "--journal", is_flag=True, help="Make a clean, separately named submission PDF."
)
@click.option(
    "--outdir",
    type=click.Path(path_type=Path, file_okay=False),
    help="Override the configured output directory for this run.",
)
def build_command(source: Path | None, journal: bool, outdir: Path | None) -> None:
    """Compile SOURCE or the current project's configured main file."""
    docker = _docker()
    cwd = Path.cwd()
    project = load_project(source, cwd=cwd, suite_root=docker.root)
    output = build(
        docker,
        project,
        (cwd / outdir).resolve() if outdir is not None else project.outdir,
        journal=journal,
    )
    click.echo(output)


@cli.command()
@click.option(
    "--build",
    "build_image",
    is_flag=True,
    help="Build the configured image before starting.",
)
def up(build_image: bool) -> None:
    """Start the shared compiler and wait for it to be ready."""
    _docker().up(build=build_image)


@cli.command()
def down() -> None:
    """Stop the shared compiler service."""
    _docker().down()


@cli.command()
def rebuild() -> None:
    """Refresh the compiler image and recreate the shared service."""
    _docker().rebuild()


@cli.command()
def doctor() -> None:
    """Report Docker, image, container, and toolchain readiness."""
    _docker().doctor()


def _fingerprint(path: Path) -> tuple[int, int]:
    info = path.stat()
    return info.st_mtime_ns, info.st_size


def _staged_tool(docker: Docker, tool: str, args: tuple[str, ...], cwd: Path) -> int:
    root = project_root(cwd, suite_root=docker.root)
    with project_lock(root / CACHE_DIR):
        staged = stage_project(root, suite_root=docker.root)
        forwarded = []
        for arg in args:
            path = Path(arg)
            if path.is_absolute() and path.is_relative_to(root):
                arg = str(staged / path.relative_to(root))
            forwarded.append(arg)
        writes_files = tool in ("tex-fmt", "tectonic")
        before = (
            {
                path: _fingerprint(path)
                for path in staged.rglob("*")
                if path.is_file() and not path.is_symlink()
            }
            if writes_files
            else {}
        )
        result = docker.run(
            (tool, *forwarded), cwd=staged / cwd.relative_to(root), check=False
        )
        if result.returncode == 0 and writes_files:
            paths = staged.rglob("*") if tool == "tectonic" else before.keys()
            for path in paths:
                if not path.is_file() or path.is_symlink():
                    continue
                original = before.get(path)
                if _fingerprint(path) == original:
                    continue
                destination = root / path.relative_to(staged)
                if original is not None and (
                    not destination.is_file()
                    or destination.is_symlink()
                    or _fingerprint(destination) != original
                ):
                    raise click.ClickException(
                        f"Source changed while running {tool}: {destination}"
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                if path.name.endswith((".synctex", ".synctex.gz")):
                    sync_synctex(
                        path,
                        destination,
                        staged_root=staged,
                        project_root=root,
                        source_cwd=staged / cwd.relative_to(root),
                    )
                else:
                    publish_file(path, destination)
        return result.returncode


def _register_tool(
    name: str, tool: str, description: str, *, hidden: bool = False
) -> None:
    @cli.command(
        name,
        help=description,
        hidden=hidden,
        add_help_option=False,
        context_settings={"ignore_unknown_options": True},
    )
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def command(args: tuple[str, ...]) -> None:
        docker = _docker()
        docker.ready()
        cwd = Path.cwd().resolve()
        if cwd.is_relative_to(docker.root):
            status = docker.run((tool, *args), cwd=cwd, check=False).returncode
        elif args in (("--help",), ("--version",)):
            status = docker.run((tool, *args), check=False).returncode
        elif tool == "texpresso":
            raise click.ClickException(
                "TeXpresso needs a project in the mounted deployment checkout."
            )
        else:
            status = _staged_tool(docker, tool, args, cwd)
        if status:
            click.get_current_context().exit(status)


_register_tool("fmt", "tex-fmt", "Format LaTeX source.")
_register_tool("check", "chktex", "Lint LaTeX source.")
_register_tool("count", "texcount", "Count words in LaTeX source.")
_register_tool("diff", "latexdiff", "Show source differences.")
_register_tool("tectonic", "tectonic", "Run Tectonic directly.")
_register_tool(
    "_texpresso", "texpresso", "Stream a TeXpresso editor session.", hidden=True
)


def main() -> None:
    try:
        cli(prog_name="paper")
    except (OSError, ProjectError, StagingError) as error:
        click.ClickException(str(error)).show()
        raise SystemExit(1) from error
    except subprocess.CalledProcessError as error:
        click.ClickException(
            f"Command failed (exit {error.returncode}). See the diagnostics above."
        ).show()
        raise SystemExit(error.returncode or 1) from error


if __name__ == "__main__":
    main()
