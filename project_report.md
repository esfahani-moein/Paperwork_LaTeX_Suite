# Paperwork LaTeX Suite: Project Report

## 1. What it is
A fast LaTeX compile service for researchers who write papers every day. Writers use VS Code on
their own machine with any extensions they like (Claude, Codex, …). One always-on Docker container
(run by OrbStack) compiles every paper in the project. Saving a file rebuilds the PDF in ~0.3 s,
so it feels close to Word. Writers never enter a container, install TeX or touch Docker.

## 2. Structure
```
project_paperwork_latex_suit/
├── paper.env            settings: engine, shell escape, TeX Live size, CPU/RAM, network
├── compose.yaml         the single compile service (+ optional frozen TeX Live 2025 service)
├── bin/paper            host shim: up|down|rebuild|new, and forwards tools into the container
├── bin/{paperbuild,tex-fmt,chktex,texcount,latexdiff,tectonic} -> paper (symlinks)
├── image/Dockerfile     Debian 13 + TeX Live (latest) + Tectonic 0.17.0 + tex-fmt 0.5.7
├── image/paperbuild     the build logic (runs inside the container)
├── papers/<name>/       one folder per paper (+ optional paper.env overrides)
├── templates/article/   starter paper copied by `bin/paper new <name>`
├── .vscode/             autosave, build-on-save, PDF tab, Fast/Journal build buttons
├── AGENTS.md, CLAUDE.md how AI agents compile and what they must not change
├── test.sh              end-to-end self-check (run after every change)
└── cont_refrence/       old reference image (qdm12/latexdevcontainer), inspiration only
```

## 3. How it works
```
VS Code / AI agent (macOS)
   │  bin/paperbuild main.tex
   ▼
bin/paper ── docker exec (same folder path) ──►  container "paper-latex"
                                                   paperbuild:
                                                   1. read settings (paper.env, % !TEX program)
                                                   2. choose engine
                                                   3. pdflatex: load cached preamble (/cache/fmt)
                                                   4. latexmk, aux files in RAM (/build)
                                                   5. only main.pdf + main.synctex.gz written back
```
- **Same-path mount:** the project folder has the same absolute path inside the container and on
  the Mac, so clicking PDF ↔ source jumps (SyncTeX) and AI agents see the same paths.
- **Speed:** the preamble is precompiled once per version (`mylatexformat`). Aux files live in RAM.
  The container stays running, so each build skips startup. The host shim makes one Docker call.
- **Several papers at once:** each document gets its own RAM build folder and a lock (`flock`).
  Papers build in parallel; autosave and an agent building the same paper are queued.
- **Engine choice**, first match wins: the paper's `paper.env` → a `% !TEX program` line in the file →
  the project's `paper.env` → auto (fontspec/unicode-math → lualatex, else pdflatex).
- **Journal build** (`--journal`): a clean, full build without the cached preamble. This is the PDF to submit.
- **Hardening:** read-only system files, non-root user, only this project folder mounted,
  shell escape off by default.

## 4. Status (tested with `./test.sh scheme-small`: PASS)
| Done | Notes |
|---|---|
| Fast build, ~0.27 s rebuild via shim | the shim itself adds ~0.1 s |
| pdflatex / lualatex / xelatex / tectonic | Tectonic's bundle ships LaTeX 2021-11: don't use it for submissions |
| Parallel papers, per-paper lock, Journal build | |
| Isolation (no host home), read-only root, refuses paths outside the project | |
| Frozen TeX Live 2025 service | configuration validated only, image never built |

Known limits (marked `shortcut:` in code):
- The cached preamble hashes only the main file. Edits to local `.sty`/`.cls` files need a Journal build.
- If the container was down, the retried call gets an empty stdin (only matters when tex-fmt reads piped input).

Not verified yet:
- The full `scheme-full` image build.
- VS Code end to end: `%WORKSPACE_FOLDER%` expansion, and which folder LaTeX Workshop builds from.
- tex-fmt formatting from inside the editor (it works from the command line).

## 5. Rules for agents developing this project
- Keep it small (ponytail): the smallest complete change, no unrequested options, comment the *why*.
- Every file starts with a header comment saying what it does.
- Latest stable versions only; check them online before pinning. Base OS: latest Debian stable.
- Never install or remove software on the host; build and test only inside OrbStack.
- Run `./test.sh scheme-small` after every change, and add a check to it for each new behavior.
- Settings belong in `paper.env` (plain KEY=VALUE, read with `val`, never sourced as code).

## 6. Roadmap: one step per agent task
Each step ends with `./test.sh` passing and a new check added for it.

| # | Step | Where | Done when |
|---|---|---|---|
| 1 | **Verify in VS Code**: open the workspace, build on save, PDF tab, SyncTeX click | `.vscode/settings.json` | Writer flow works; fix the tool command if placeholders don't expand |
| 2 | **Build the full image** (`scheme-full`) and the TL2025 service | `image/`, `compose.yaml` | Both build; measure image sizes |
| 3 | **Formatter in the editor**: tex-fmt via the shim | `.vscode/settings.json` | Format Document works |
| 4 | **Live preview while typing** with TeXpresso (built on the Tectonic engine) | `image/Dockerfile`, `.vscode/` | Preview updates without saving |
| 5 | **Plain-English errors**: translate common LaTeX errors in paperbuild output | `image/paperbuild` | Top 10 errors are readable |
| 6 | **Full preamble tracking**: hash every preamble input via the `.fls` file (removes shortcut 1) | `image/paperbuild` | Editing a local `.sty` triggers a new format |
| 7 | **`paperd`, a Rust daemon** replacing docker exec: file watching, background preamble rebuilds, socket API | new `paperd/` crate | Rebuild under 0.15 s end to end |
| 8 | **Submit pack**: fonts-embedded check, page count, arXiv zip with `.bbl` | `paperbuild --submit` | Zip compiles on a clean TeX Live |
| 9 | **Writer tools**: templates (IEEE/ACM/Elsevier/Springer), latexdiff "show changes", DOI → BibTeX | `templates/`, `bin/paper` | One command each |
| 10 | **CI + registry**: weekly multi-arch (amd64/arm64) image build, tagged per TeX Live year | `.github/workflows/` | Writers pull instead of building |
| 11 | **Server mode**: browser VS Code or a remote `paperd` for writers without Docker | new service | Zero-install access |
