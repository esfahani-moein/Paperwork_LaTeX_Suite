# Paperwork LaTeX Suite

A VS Code LaTeX workspace with one always-on Docker container. Authors do not install TeX Live,
Tectonic, or TeXpresso on their computer.

## Features

- Fast build on save with pdfLaTeX, LuaLaTeX, or XeLaTeX.
- Clean Journal builds for submission.
- Optional Tectonic builds and TeXpresso live preview.
- Independent papers and reusable templates.
- Shared formatting, linting, word-count, and source-diff tools.
- Non-root, read-only container with shell escape disabled by default.

## Quickstart

1. Install and start [OrbStack](https://orbstack.dev/) or Docker.
2. Open this folder in VS Code and install the recommended extensions.
3. Create and build a paper:

   ```sh
   bin/paper new my-paper
   bin/paper build papers/my-paper/main.tex
   ```

4. Open `papers/my-paper/main.tex`, write, and save. LaTeX Workshop shows the PDF.

The container starts automatically when a tool needs it. `bin/paper doctor` checks the setup.

## Commands

```text
bin/paper new <name> [--template <name>]
bin/paper build [--journal] <file.tex>
bin/paper fmt <file.tex>
bin/paper check <file.tex>
bin/paper count <file.tex>
bin/paper diff <old.tex> <new.tex>
bin/paper tectonic [arguments]
bin/paper up | down | rebuild | doctor
```

Use **Journal build** for the PDF you submit. It performs a clean full build without the cached
preamble. Fast builds keep auxiliary files in RAM and cache the pdfLaTeX preamble.

## Optional TeXpresso live preview

Open a paper's root `main.tex` and run **TeXpresso: Start Document** from the VS Code command
palette. The engine runs in `paper-latex`; only the extension and preview UI run on the host.

TeXpresso uses a custom XeTeX engine. It is a preview, not proof that a pdfLaTeX, LuaLaTeX, or
journal build is correct. Bibliography changes may require **TeXpresso: External Compile and
Refresh** or a normal build.

For continuous live editing, change `latex-workshop.latex.autoBuild.run` to `never` in workspace
settings to avoid running a second full build after every autosave. Fast and Journal build buttons
remain available.

## Paper settings

Edit `papers/<name>/paper.env`:

```sh
ENGINE=auto       # auto | pdflatex | lualatex | xelatex | tectonic
MAIN=main.tex
SHELL_ESCAPE=0
```

`auto` selects LuaLaTeX when the main file loads `fontspec` or `unicode-math`, otherwise pdfLaTeX.
Use an explicit engine for journal templates that require one. Tectonic uses its own package bundle;
check it against journal requirements before submission.

Keep the main file directly inside `papers/<name>/` when using the supplied TeXpresso configuration.

## TeX Live version

The project-wide `paper.env` selects the one distribution available in the container:

```sh
TEXLIVE=latest    # current release when the image is built
# TEXLIVE=2025    # frozen annual release
```

Apply a change explicitly:

```sh
bin/paper rebuild
```

This rebuilds the image and replaces the container for **all papers**. `latest` does not update a
running container by itself. The image includes TeXpresso 2.0.1 with its matched native engine;
both AMD64 and ARM64 bundles are checksum-verified.

## Project layout

```text
bin/paper              public command-line interface
bin/texpresso          internal VS Code-to-container bridge
image/                 Docker image and internal paperbuild implementation
papers/                independent author papers
templates/             paper scaffolds
compose.yaml           one shared paper-latex service
paper.env              project-wide image and container settings
.vscode/               editor integration
test.sh                end-to-end infrastructure check
```

Run `./test.sh scheme-small` for a smaller verification build, or `./test.sh` for the full image.
