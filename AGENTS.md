# Notes for AI agents (Claude Code, Codex, ...)

This repo is a LaTeX writing workspace. TeX is NOT installed on the host; it runs in the
`paper-latex` container. Always use the shims in `bin/` from inside this folder.

- Papers live in `papers/<name>/`. New paper: `bin/paper new <name>`.
- Compile after editing: `bin/paperbuild papers/<name>/main.tex` (non-zero exit = errors; read the output).
- Submission-quality build: `bin/paperbuild --journal papers/<name>/main.tex`.
- Format: `bin/tex-fmt <file>`; lint: `bin/chktex <file>`; word count: `bin/texcount <file>`.
- Settings: `paper.env` (project) and `papers/<name>/paper.env` (per paper). Don't change
  `SHELL_ESCAPE` or `NETWORK` without asking the user.
- Never edit generated files (`*.pdf`, `*.synctex.gz`).
