# Notes for AI agents

This repo is a LaTeX writing workspace. TeX is NOT installed on the host; every tool runs in the
single `paper-latex` container. Use `bin/paper` from inside this folder.

- Papers live in `papers/<name>/`. New paper: `bin/paper new <name>`.
- Compile after editing: `bin/paper build papers/<name>/main.tex` (non-zero exit = errors).
- Submission build: `bin/paper build --journal papers/<name>/main.tex`.
- Format: `bin/paper fmt <file>`; lint: `bin/paper check <file>`; word count: `bin/paper count <file>`.
- Settings: `paper.env` (project) and `papers/<name>/paper.env` (per paper).
- `TEXLIVE` and `TEXLIVE_SCHEME` are project-wide image settings; apply them with `bin/paper rebuild`.
- Don't change `SHELL_ESCAPE` or `NETWORK` without asking the user.
- Never edit generated files (`*.pdf`, `*.synctex.gz`).
- Run `./test.sh scheme-small` after infrastructure changes.
