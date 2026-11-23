# Paperwork LaTeX Suite

One Docker service compiles all LaTeX projects. CLI finds each project's settings, runs the compiler in Docker, and publishes the finished PDF to your filesystem.

## Set up

Use a Docker runtime with Compose, Git, and uv. From the suite checkout, `uv sync --locked` sets up the development environment. The checkout command is `bin/paper`. To use `paper` from any directory, install the checkout with `uv tool install /path/to/suite` and set `PAPERSUITE_HOME` to that deployment checkout. The installed command runs directly from your PATH.

```sh
export PAPERSUITE_HOME=/path/to/suite
cd ~/research
paper new my-paper
cd my-paper
paper build
paper build --journal
```

`paper new` creates `main.tex`, `paper.toml`, `.paper-cache/`, `publication/`, and a Git repository. Its `.gitignore` excludes generated PDFs, SyncTeX, and the cache. Add a Git ignore exception for source figures you track as PDFs.

## Build and publish

Run `paper build` from anywhere in the paper or pass a source file explicitly. The CLI looks for the nearest paper settings and runs the engine from the main file's directory to preserve relative LaTeX inputs. Existing `paper.env` settings are read during migration. Add `paper.toml` to set the new options.

```toml
[build]
main = "main.tex"
engine = "auto"
outdir = "publication"

# [journal]
# engine = "pdflatex"
# toolchain = "texlive-2025"
```

- `main` is relative to the project root.
- `engine` accepts `auto`, `pdflatex`, `lualatex`, `xelatex`, or `tectonic`. Automatic selection honors a source `% !TEX program` directive and uses LuaLaTeX for `fontspec` or `unicode-math`.
- `outdir` accepts a project-relative path or an absolute path. For a one-off override, `paper build --outdir .` publishes in your current directory.
- Journal builds use fresh scratch space and a TeX Live engine. An optional `toolchain` such as `texlive-2025` checks the running image version. Set a journal engine explicitly if the daily engine is Tectonic.

With the default settings, daily and journal builds write `publication/main.pdf` and `publication/journal_main.pdf`. SyncTeX is published next to the PDF. A failed compile keeps the last successful publication. Daily builds reuse `latexmk` state, so unchanged documents can skip TeX entirely.

## Shared compiler

Docker-backed commands check the container first. In a terminal, `paper` asks before building a missing image or starting a stopped service. Editors and CI receive an error with a startup command.

| Command | Purpose |
| --- | --- |
| `paper doctor` | Report the Docker daemon, configured image, container, and compiler versions. |
| `paper up` / `paper up --build` | Start with the existing image, or build it first. |
| `paper down` / `paper rebuild` | Stop the shared service, or refresh its image and recreate it. |
| `paper fmt`, `check`, `count`, `diff`, `tectonic` | Run the bundled authoring tools. Pass tool options through the command. |

`paper.env` in the deployment checkout selects the TeX Live distribution and container resources. `TEXLIVE=latest` uses the current release when the image builds. A historical year selects that year's frozen repository when available. Apply image changes with `paper rebuild`.

Projects inside the deployment checkout use its existing bind mount. Other local projects are mirrored incrementally into `.paper-state/` in the deployment checkout, where their compiler caches also live. The CLI copies finished artifacts to the configured output directory. Use a dedicated directory for each paper and keep staged sources and their dependencies within that directory. The compiler is for trusted local inputs.

## Editors

For papers with `main.tex` in the project root, the supplied LaTeX Workshop recipes build to `publication/`. Set LaTeX Workshop's output directory to match the resolved `outdir` if you customize it or move `main.tex` into a subdirectory.

TeXpresso live preview uses the existing `bin/texpresso` bridge for papers in the mounted checkout. For continuous TeXpresso preview, turn off LaTeX Workshop build-on-save to avoid duplicate work. Use a regular build to refresh bibliography output and a journal build before submission.
