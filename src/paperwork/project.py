"""Discover and scaffold independent LaTeX projects."""

import subprocess
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory

ENGINES = ("pdflatex", "lualatex", "xelatex", "tectonic")
CACHE_DIR = ".paper-cache"
PUBLICATION_DIR = "publication"


class ProjectError(Exception):
    """A project cannot be found, read, or created."""


@dataclass(frozen=True, slots=True)
class Project:
    root: Path
    source: Path
    engine: str | None
    outdir: Path
    cache_dir: Path
    journal_engine: str | None
    journal_toolchain: str | None
    shell_escape: bool
    default_engine: str | None


def _legacy_settings(path: Path) -> dict[str, str]:
    settings = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            key, separator, rest = line.partition("#")[0].partition("=")
            if separator:
                words = rest.split(maxsplit=1)
                settings[key.strip()] = words[0] if words and words[0] != "auto" else ""
    return settings


def _table(settings: dict[str, object], name: str) -> dict[str, object]:
    table = settings.get(name, {})
    if not isinstance(table, dict):
        raise ProjectError(f"paper.toml: [{name}] must be a table")
    return table


def _reject_unknown(
    settings: dict[str, object], allowed: set[str], section: str
) -> None:
    unknown = settings.keys() - allowed
    if unknown:
        raise ProjectError(
            f"paper.toml{section}: unknown settings: {', '.join(sorted(unknown))}"
        )


def _text(settings: dict[str, object], name: str, default: str = "") -> str:
    value = settings.get(name, default)
    if (
        not isinstance(value, str)
        or "\0" in value
        or (name in settings and not value.strip())
    ):
        raise ProjectError(f"paper.toml: {name} must be a nonempty string")
    return value


def _engine(value: str, name: str) -> str | None:
    if value in ("", "auto"):
        return None
    if value not in ENGINES:
        raise ProjectError(
            f"{name}: unknown engine {value!r} (use auto or {', '.join(ENGINES)})"
        )
    return value


def _local_path(root: Path, value: str, name: str) -> Path:
    relative = Path(value)
    path = (root / relative).resolve()
    if relative.is_absolute() or path == root or not path.is_relative_to(root):
        raise ProjectError(f"{name} must be a path inside the project")
    return path


def project_root(start: Path, *, suite_root: Path) -> Path:
    """Find the nearest project marker, excluding the deployment settings."""
    start, suite_root = start.resolve(), suite_root.resolve()
    for parent in (start, *start.parents):
        if (parent / "paper.toml").is_file() or (
            parent != suite_root and (parent / "paper.env").is_file()
        ):
            return parent
    return start


def load_project(source: Path | None, *, cwd: Path, suite_root: Path) -> Project:
    """Read the nearest project settings, or use defaults for a standalone file."""
    cwd, suite_root = cwd.resolve(), suite_root.resolve()
    explicit = (cwd / source).resolve() if source is not None else None
    start = explicit.parent if explicit is not None else cwd
    root = project_root(start, suite_root=suite_root)
    settings_path = root / "paper.toml"

    try:
        defaults = _legacy_settings(suite_root / "paper.env")
        legacy = _legacy_settings(root / "paper.env") if root != suite_root else {}
        if settings_path.is_file():
            with settings_path.open("rb") as config_file:
                settings = tomllib.load(config_file)
        else:
            settings = {}
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ProjectError(f"could not read project settings: {error}") from error

    _reject_unknown(settings, {"build", "journal"}, "")
    build, journal = _table(settings, "build"), _table(settings, "journal")
    _reject_unknown(build, {"main", "engine", "outdir"}, " [build]")
    _reject_unknown(journal, {"engine", "toolchain"}, " [journal]")
    if explicit is None:
        main = _text(build, "main", legacy.get("MAIN") or "main.tex")
        source = (
            _local_path(root, main, "Main source")
            if "main" in build
            else (root / main).resolve()
        )
    else:
        source = explicit
    if not source.is_relative_to(root):
        raise ProjectError("The main source must be inside the project")
    if not source.is_file():
        raise ProjectError(f"LaTeX source does not exist: {source}")

    cache_dir = _local_path(root, CACHE_DIR, CACHE_DIR)
    outdir = (root / _text(build, "outdir", PUBLICATION_DIR)).resolve()
    if outdir.is_relative_to(cache_dir):
        raise ProjectError("paper.toml: build.outdir overlaps the project cache")
    if outdir.exists() and not outdir.is_dir():
        raise ProjectError(f"paper.toml: build.outdir is not a directory: {outdir}")
    return Project(
        root=root,
        source=source,
        engine=_engine(
            _text(build, "engine", legacy.get("ENGINE", "")), "project engine"
        ),
        outdir=outdir,
        cache_dir=cache_dir,
        journal_engine=_engine(_text(journal, "engine"), "journal engine"),
        journal_toolchain=_text(journal, "toolchain") or None,
        shell_escape=(legacy.get("SHELL_ESCAPE") or defaults.get("SHELL_ESCAPE"))
        == "1",
        default_engine=_engine(defaults.get("ENGINE", ""), "suite engine"),
    )


def new_project(name: str, template: str = "article", *, cwd: Path) -> Path:
    """Create the project below the caller's directory and initialize Git."""
    for label, value in (("project", name), ("template", template)):
        if value in ("", ".", "..") or Path(value).name != value or "\0" in value:
            raise ProjectError(f"invalid {label} name: {value!r}")
    scaffold = files("paperwork").joinpath("templates", template)
    if not scaffold.is_dir():
        raise ProjectError(f"unknown template: {template}")
    git = which("git")
    if git is None:
        raise ProjectError("Git is required to initialize a new project")

    destination = cwd.resolve() / name
    try:
        with TemporaryDirectory(prefix=".paper-new-", dir=destination.parent) as temp:
            staged = Path(temp) / "project"
            staged.mkdir()
            for file in scaffold.iterdir():
                (staged / file.name).write_bytes(file.read_bytes())
            (staged / CACHE_DIR).mkdir()
            (staged / PUBLICATION_DIR).mkdir()
            subprocess.run([git, "init", "--quiet"], cwd=staged, check=True)

            # Claim the destination so two scaffolds cannot replace each other.
            destination.mkdir()
            try:
                staged.replace(destination)
            except OSError:
                destination.rmdir()
                raise
    except FileExistsError as error:
        raise ProjectError(f"already exists: {destination}") from error
    except (OSError, subprocess.CalledProcessError) as error:
        raise ProjectError(f"could not initialize {destination}: {error}") from error
    return destination
