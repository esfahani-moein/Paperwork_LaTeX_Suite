# Paperwork LaTeX Suite

One Docker service compiles all LaTeX projects. CLI finds each project's settings, runs the compiler in Docker, and publishes the finished PDF to your filesystem.
Use `paper` to turn LaTeX files into PDFs. All your LaTeX papers share one Docker compiler, so you can edit your `.tex` files in any editor and build with CLI.

## Install

Install Git, uv, and a Docker runtime with Compose, then start Docker. [Git downloads](https://git-scm.com/downloads) · [uv installation](https://docs.astral.sh/uv/getting-started/installation/) · [Docker installation](https://docs.docker.com/get-started/get-docker/)

Open a terminal and run these commands. If you already have the repository, open its folder and start with `uv tool install`.

```sh
cd "$HOME"
git clone https://github.com/esfahani-moein/Paperwork_LaTeX_Suite.git
cd Paperwork_LaTeX_Suite
uv tool install --python '>=3.15.2' .
export PAPERSUITE_HOME="$(pwd -P)"
paper --help
```

`PAPERSUITE_HOME` tells `paper` where to find the compiler setup. To keep it set in new terminals, add `export PAPERSUITE_HOME="$HOME/Paperwork_LaTeX_Suite"` to your shell startup file, such as `~/.zshrc` on macOS or `~/.bashrc` on Linux. Use your own checkout path if it differs.

### Check or reinstall

- If `paper` is missing, run `uv tool update-shell`, open a new terminal, set `PAPERSUITE_HOME` again, and try `paper --help`. [uv tool installation guide](https://docs.astral.sh/uv/guides/tools/#installing-tools)
- If builds fail to start, run `paper doctor`. Start Docker if the daemon is unavailable, run `paper up --build` if the image is missing, or run `paper up` if the compiler is stopped.
- To reinstall the CLI, open the repository folder and run `uv tool install --reinstall --python '>=3.15.2' .`. Then check `paper --help` again.

## Build your first PDF

Go to a folder where you keep your work, then create and build a paper.

```sh
paper new my-paper
cd my-paper
paper build
```

On the first build, `paper` may ask to build the compiler image or start the service. Open `publication/main.pdf` when the build finishes. Edit `main.tex` and run `paper build` again to update it.

`paper new` also creates a Git repository. Its `.gitignore` excludes PDFs, SyncTeX files, and the build cache. Add an exception for any PDF figures you want to track in Git.

## Paper settings

Edit `paper.toml` in your paper folder. A new paper starts with these settings.

```toml
[build]
main = "main.tex"
engine = "auto"
outdir = "publication"
```

- `main` is the `.tex` file to build. Its path is relative to the paper folder.
- `engine = "auto"` uses **pdfLaTeX** with the standard suite settings. Set `lualatex`, `xelatex`, or `tectonic` explicitly when your template requires a different engine. If your source has a `% !TEX program` comment, set that engine in `paper.toml` to use it with `paper`.
- `outdir` is where PDFs go. Use a path relative to the paper folder or an absolute path. For a one-time override, run `paper build --outdir .` to save to the current directory.

Run `paper build` from anywhere inside the paper folder, or pass a source file such as `paper build chapters/appendix.tex`. Existing papers can still use their `paper.env` settings.

## Check a submission

Run `paper build --journal` for a clean build. Open `publication/journal_main.pdf` with the default settings. A failed build keeps your last successful PDF.

Paperwork defaults to pdfLaTeX for arXiv papers. Check arXiv’s submission instructions and preview after uploading your source. If a venue requires a specific engine, set it under `[journal]` in `paper.toml`. You can also set `toolchain = "texlive-2025"` there to check the running image version. For a daily Tectonic build, choose a TeX Live engine for the journal build. [arXiv TeX submission guide](https://info.arxiv.org/help/submit_tex.html)

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
