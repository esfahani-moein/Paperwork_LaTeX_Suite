"""Compile through the shared container and publish completed artifacts."""

import fcntl
import hashlib
import os
import re
import shutil
import subprocess
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import click

from .docker import Docker
from .project import Project
from .staging import stage_project, sync_synctex

_MODES = {"pdflatex": "-pdf", "lualatex": "-pdflua", "xelatex": "-pdfxe"}


def _engine(project: Project, journal: bool) -> str:
    return (
        (project.journal_engine if journal else None)
        or project.engine
        or project.default_engine
        or "pdflatex"
    )


@contextmanager
def project_lock(cache: Path) -> Generator[None]:
    """Serialize builds and source writeback for a project on this host."""
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def publish_file(source: Path, dest: Path) -> None:
    """Replace the destination only after the complete file is on its filesystem."""
    if dest.is_file() and not dest.is_symlink():
        previous, current = dest.stat(), source.stat()
        if (previous.st_mtime_ns, previous.st_size) == (
            current.st_mtime_ns,
            current.st_size,
        ):
            return
    with NamedTemporaryFile(dir=dest.parent, delete=False) as output:
        staged = Path(output.name)
    try:
        shutil.copy2(source, staged)
        os.replace(staged, dest)
    finally:
        staged.unlink(missing_ok=True)


def _command(
    engine: str, source: str, scratch: Path, *, shell_escape: bool, offline: bool
) -> list[str]:
    if engine == "tectonic":
        command = ["tectonic", "--synctex", "--keep-logs", "--outdir", str(scratch)]
        if offline:
            command.append("-C")
        if shell_escape:
            command.extend(("-Z", "shell-escape"))
    else:
        command = [
            "latexmk",
            _MODES[engine],
            f"-outdir={scratch}",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "-synctex=1",
        ]
        if shell_escape:
            command.append("-shell-escape")
    return [*command, f"./{source}"]


def _report_failure(log: Path, *, journal: bool) -> None:
    if not log.is_file():
        return
    with log.open(errors="replace") as lines:
        for line in lines:
            if line.startswith("! ") or re.match(r"^.+\.\w+:\d+: ", line):
                click.echo(f"TeX: {line.removeprefix('! ').strip()}", err=True)
                break
    if not journal:
        click.echo(f"TeX log: {log}", err=True)


def build(docker: Docker, project: Project, outdir: Path, *, journal: bool) -> Path:
    if outdir.is_relative_to(project.cache_dir):
        raise click.ClickException("The output directory overlaps the project cache.")
    engine = _engine(project, journal)
    if engine not in (*_MODES, "tectonic"):
        raise click.ClickException(
            f"Unknown LaTeX engine {engine!r}. Set [build].engine in paper.toml."
        )
    if journal and engine == "tectonic":
        raise click.ClickException(
            "Set [journal].engine to a TeX Live engine for submission builds."
        )

    docker.ready()
    if journal and project.journal_toolchain:
        version = docker.run(("latex", "--version"), capture_output=True).stdout
        release = re.search(r"TeX Live (\d{4})", version)
        current = f"texlive-{release[1]}" if release else "unknown"
        if project.journal_toolchain != current:
            raise click.ClickException(
                f"Journal needs {project.journal_toolchain}; the service provides {current}. "
                "Select the required TeX Live image before building."
            )

    stem = project.source.stem
    published_stem = f"journal_{stem}" if journal else stem
    output = outdir / f"{published_stem}.pdf"
    with project_lock(project.cache_dir):
        excluded = [
            project.cache_dir,
            *(
                folder / name
                for folder in {outdir, project.outdir}
                for name in (f"{stem}.pdf", f"journal_{stem}.pdf")
            ),
        ]
        staged_root = stage_project(
            project.root, suite_root=docker.root, excluded=excluded
        )
        relative_source = project.source.relative_to(project.root)
        source_cwd = staged_root / relative_source.parent
        cache = (
            project.cache_dir
            if staged_root == project.root
            else staged_root.parent / "cache"
        )
        cache.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(
            f"{docker.image_id}\0{engine}\0{project.shell_escape}\0{relative_source}".encode()
        ).hexdigest()[:24]
        job_dir = (
            TemporaryDirectory(prefix="journal-", dir=cache)
            if journal
            else nullcontext(str(cache / key))
        )
        with job_dir as location:
            scratch = Path(location)
            scratch.mkdir(exist_ok=True)
            command = _command(
                engine,
                project.source.name,
                scratch,
                shell_escape=project.shell_escape,
                offline=docker.network_mode == "none",
            )
            success = scratch / ".paper-build-ok"
            track_success = not journal and engine in _MODES
            if track_success:
                # A rule database can outlive a failed or interrupted build.
                if not success.exists() and (scratch / f"{stem}.fdb_latexmk").exists():
                    command.insert(1, "-g")
                success.unlink(missing_ok=True)
            try:
                docker.run(command, cwd=source_cwd)
            except subprocess.CalledProcessError:
                _report_failure(scratch / f"{stem}.log", journal=journal)
                raise
            pdf = scratch / f"{stem}.pdf"
            if not pdf.is_file() or not pdf.stat().st_size:
                raise click.ClickException(
                    f"Build produced no PDF for {project.source}."
                )
            if track_success:
                success.touch()
            outdir.mkdir(parents=True, exist_ok=True)
            synctex = scratch / f"{stem}.synctex.gz"
            if not synctex.is_file():
                synctex = scratch / f"{stem}.synctex"
            if synctex.is_file():
                sync_synctex(
                    synctex,
                    output.with_suffix(".synctex.gz"),
                    staged_root=staged_root,
                    project_root=project.root,
                    source_cwd=source_cwd,
                )
            publish_file(pdf, output)
    return output
