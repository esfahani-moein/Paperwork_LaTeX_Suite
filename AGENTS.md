# Notes for AI agents

This repo is a LaTeX writing workspace. TeX is NOT installed on the host; every tool runs in the
single `paper-latex` container. Use `bin/paper` or the installed `paper` command.

- Create a paper in the current directory with `paper new <name>`.
- Compile after editing with `paper build [<file.tex>]` (non-zero exit = errors).
- Run `paper build --journal` for a clean `publication/journal_main.pdf` by default.
- Format: `bin/paper fmt <file>`; lint: `bin/paper check <file>`; word count: `bin/paper count <file>`.
- Settings live in the suite's `paper.env` and each paper's `paper.toml`. The CLI also reads legacy per-paper `paper.env`.
- `TEXLIVE` and `TEXLIVE_SCHEME` are project-wide image settings; apply them with `bin/paper rebuild`.
- Don't change `SHELL_ESCAPE` or `NETWORK` without asking the user.
- Never edit generated files (`*.pdf`, `*.synctex.gz`).
- Run `./test.sh scheme-small` after infrastructure changes.
- Run `uv run ruff check src`, `uv run ruff format --check src`, and `uv run ty check src` after Python changes.
