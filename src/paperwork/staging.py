"""Mirror external projects into the shared container's bind mount."""

import gzip
import hashlib
import os
import shutil
import stat
from collections.abc import Iterable, Sequence
from contextlib import nullcontext
from pathlib import Path
from tempfile import NamedTemporaryFile

_IGNORED = {".git", ".paper-cache", ".paper-state"}
_GENERATED = (".fdb_latexmk", ".fls", ".synctex", ".synctex.gz")


class StagingError(Exception):
    """A source cannot be mirrored into the container's workspace."""


def stage_project(
    root: Path, *, suite_root: Path, excluded: Sequence[Path] = ()
) -> Path:
    """Return the in-container source path, retaining source mtimes across builds.

    The caller serializes staging and compilation for this project.
    """
    root, suite_root = root.resolve(strict=True), suite_root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    if root.is_relative_to(suite_root):
        return root

    key = hashlib.sha256(os.fsencode(root)).hexdigest()[:24]
    staged_root = suite_root / ".paper-state" / key / "sources"
    for directory in (staged_root.parent.parent, staged_root.parent, staged_root):
        if directory.is_symlink():
            raise StagingError(
                f"paper staging directory is a symbolic link: {directory}"
            )
        directory.mkdir(exist_ok=True)
    ignored = set()
    if suite_root.is_relative_to(root):
        ignored.add(suite_root.relative_to(root))
    for path in excluded:
        path = Path(os.path.abspath(root / path))
        if path != root and path.is_relative_to(root):
            ignored.add(path.relative_to(root))

    def skip(relative: Path) -> bool:
        return (
            not _IGNORED.isdisjoint(relative.parts)
            or relative.name.endswith(_GENERATED)
            or any(relative.is_relative_to(path) for path in ignored)
        )

    def mirror(source: Path, destination: Path) -> None:
        names = set()
        with os.scandir(source) as entries:
            for entry in entries:
                path = Path(entry.path)
                if skip(path.relative_to(root)):
                    continue
                names.add(entry.name)
                target = destination / entry.name
                metadata = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(metadata.st_mode):
                    if target.is_symlink() or not target.is_dir():
                        target.unlink(missing_ok=True)
                        target.mkdir()
                    mirror(path, target)
                elif stat.S_ISREG(metadata.st_mode):
                    _copy_file(path, target, metadata)
                elif stat.S_ISLNK(metadata.st_mode):
                    linked = path.resolve()
                    if not linked.is_relative_to(root) or skip(
                        linked.relative_to(root)
                    ):
                        raise StagingError(
                            f"symbolic link leaves staged project inputs: {path}"
                        )
                    if not linked.exists():
                        raise StagingError(f"symbolic link has no target: {path}")
                    value = os.path.relpath(
                        staged_root / linked.relative_to(root), target.parent
                    )
                    if not target.is_symlink() or os.readlink(target) != value:
                        _remove_entry(target)
                        target.symlink_to(value)
                else:
                    raise StagingError(
                        f"unsupported project input: {path}; use a regular file"
                    )
        for stale in destination.iterdir():
            if stale.name not in names:
                _remove_entry(stale)

    mirror(root, staged_root)
    return staged_root


def _remove_entry(path: Path) -> None:
    if not path.is_symlink() and path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _copy_file(source: Path, destination: Path, metadata: os.stat_result) -> None:
    try:
        previous = destination.lstat()
    except FileNotFoundError:
        pass
    else:
        # shortcut: a same-size replacement with an explicitly preserved mtime needs a fresh mirror.
        if (
            previous.st_mode == metadata.st_mode
            and previous.st_size == metadata.st_size
            and previous.st_mtime_ns == metadata.st_mtime_ns
        ):
            return
        if stat.S_ISDIR(previous.st_mode):
            shutil.rmtree(destination)
    with NamedTemporaryFile(dir=destination.parent, delete_on_close=False) as temporary:
        temporary.close()
        shutil.copy2(source, temporary.name, follow_symlinks=False)
        os.replace(temporary.name, destination)


def sync_synctex(
    source: Path,
    destination: Path,
    *,
    staged_root: Path,
    project_root: Path,
    source_cwd: Path | None = None,
) -> None:
    """Publish SyncTeX with host paths so editor navigation survives staging."""
    if source == destination:
        return
    metadata = source.stat()
    if destination.is_file() and destination.stat().st_mtime_ns == metadata.st_mtime_ns:
        return

    read = gzip.open if source.suffix == ".gz" else Path.open
    with (
        read(source, "rb") as incoming,
        NamedTemporaryFile(dir=destination.parent, delete_on_close=False) as temporary,
    ):
        write = (
            gzip.GzipFile(
                filename="", fileobj=temporary, mode="wb", compresslevel=1, mtime=0
            )
            if destination.suffix == ".gz"
            else nullcontext(temporary)
        )
        with write as outgoing:
            lines = _synctex_lines(
                incoming, staged_root, project_root, source_cwd or staged_root
            )
            outgoing.writelines(lines)
        temporary.close()
        os.chmod(temporary.name, stat.S_IMODE(metadata.st_mode))
        os.utime(temporary.name, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        os.replace(temporary.name, destination)


def _synctex_lines(
    lines: Iterable[bytes], staged_root: Path, project_root: Path, source_cwd: Path
) -> Iterable[bytes]:
    offset_delta = 0
    for original in lines:
        line = original
        if line.startswith(b"Input:"):
            heading, separator, path = line.rstrip(b"\n")[6:].partition(b":")
            if separator and path:
                absolute = Path(os.path.abspath(source_cwd / os.fsdecode(path)))
                if absolute.is_relative_to(staged_root):
                    mapped = project_root / absolute.relative_to(staged_root)
                    line = b"Input:" + heading + b":" + os.fsencode(mapped) + b"\n"
        elif line.startswith(b"!") and line[1:].strip().isdigit():
            # An anchor counts uncompressed bytes since the start of the previous anchor.
            if offset_delta:
                line = f"!{int(line[1:]) + offset_delta}\n".encode()
            offset_delta = 0
        offset_delta += len(line) - len(original)
        yield line
