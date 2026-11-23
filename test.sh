#!/bin/sh
# Exercise the public CLI against a disposable deployment and paper.
set -eu
root=$(CDPATH='' cd "$(dirname "$0")" && pwd -P)
paper=$root/bin/paper
scratch=$(mktemp -d /tmp/paper-test.XXXXXX)
scratch=$(cd "$scratch" && pwd -P)
export COMPOSE_PROJECT_NAME=paper_test_$$ PAPER_CONTAINER_NAME=paper-test-$$
export PAPERSUITE_HOME=$scratch/deploy
export TEXLIVE_SCHEME=${1:-scheme-full}
export PAPER_IMAGE=${PAPER_TEST_IMAGE:-paper-latex:smoke-$TEXLIVE_SCHEME}
mkdir "$PAPERSUITE_HOME"
cp "$root/compose.yaml" "$root/paper.env" "$PAPERSUITE_HOME/"
cp -R "$root/image" "$PAPERSUITE_HOME/image"

cleanup() {
  "$paper" down >/dev/null 2>&1 || true
  docker volume rm "${COMPOSE_PROJECT_NAME}_cache" >/dev/null 2>&1 || true
  rm -rf "$scratch"
}
trap cleanup EXIT

cd "$scratch"
"$paper" new 'test paper'
cd 'test paper'
test -d .git
git check-ignore -q .paper-cache/aux
git check-ignore -q publication/main.pdf
{ printf '%s\n' '\RequirePackage{nicefrac}' '\RequirePackage{placeins}'; cat main.tex; } >"$scratch/template.tex"
cp "$scratch/template.tex" main.tex
if "$paper" build </dev/null >"$scratch/not-ready" 2>&1; then
  echo 'Expected a noninteractive readiness error' >&2
  exit 1
fi
grep -q 'paper up' "$scratch/not-ready"
if [ -n "${PAPER_TEST_IMAGE:-}" ]; then "$paper" up; else "$paper" up --build; fi

compile() {
  "$paper" build "$@" >"$scratch/compile.log" 2>&1 || { tail -n 40 "$scratch/compile.log" >&2; return 1; }
}

compile
compile
grep -q 'Nothing to do' "$scratch/compile.log"
compile --journal
test -s publication/main.pdf
test -s publication/journal_main.pdf
gzip -dc publication/main.synctex.gz | grep -F "$(pwd -P)/main.tex" >/dev/null
compile --outdir "$scratch/override"
test -s "$scratch/override/main.pdf"
mkdir sections
cp main.tex sections/appendix.tex
(cd sections && compile --outdir . appendix.tex && test -s appendix.pdf)
cp paper.toml "$scratch/default.toml"
printf '[build]\noutdir = "../comparison"\n' >paper.toml
compile
test -s "$scratch/comparison/main.pdf"
cp "$scratch/default.toml" paper.toml

cp publication/main.pdf "$scratch/last-good.pdf"
cp main.tex "$scratch/source.tex"
{ printf '%s\n' '\thisCommandDoesNotExist'; cat "$scratch/source.tex"; } >main.tex
if "$paper" build >"$scratch/bad-build" 2>&1; then
  echo 'Expected an invalid TeX document to fail' >&2
  exit 1
fi
cmp publication/main.pdf "$scratch/last-good.pdf"
if "$paper" build >"$scratch/retry" 2>&1; then
  echo 'Expected the unchanged invalid document to fail again' >&2
  exit 1
fi
grep -q 'Running.*pdflatex' "$scratch/retry"
grep -q '^TeX:.*Undefined control sequence' "$scratch/retry"
cp "$scratch/source.tex" main.tex
compile
"$paper" doctor
echo PASS
