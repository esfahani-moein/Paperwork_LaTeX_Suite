#!/bin/sh
# ---------------------------------------------------------------------------
# End-to-end infrastructure check, using the same host CLI as authors and agents.
# Usage: ./test.sh [scheme]     scheme-small reduces the verification download.
# ---------------------------------------------------------------------------
set -eu
cd "$(dirname "$0")"; root=$(pwd -P)
[ -n "${1:-}" ] && export TEXLIVE_SCHEME="$1"
id=$$; a=_test_${id}_a; b=_test_${id}_b; c=_test_${id}_c
logs=$(mktemp -d /tmp/paper-test.XXXXXX)
trap 'rm -rf "$root/papers/$a" "$root/papers/$b" "$root/papers/$c" "$logs"' EXIT
ok() { echo "ok   $*"; }
fail() { echo "FAIL $*"; exit 1; }

bin/paper rebuild >"$logs/image.log" 2>&1 || { tail -50 "$logs/image.log"; fail "image build"; }
bin/paper new "$a" --template article >/dev/null
bin/paper new "$b" >/dev/null
bin/paper new "$c" >/dev/null
echo ENGINE=xelatex > "papers/$b/paper.env"
echo ENGINE=tectonic > "papers/$c/paper.env"

# Normal and cached builds from the paper folder, with no auxiliary-file clutter.
cd "papers/$a"; bin=../../bin
$bin/paper build main.tex >"$logs/a.log" 2>&1 || { tail -20 "$logs/a.log"; fail "first build"; }
sed -i '' 's/Start writing/Keep writing/' main.tex
$bin/paper build main.tex >/dev/null 2>&1 || fail "cached rebuild"
[ "$(ls | sort | tr '\n' ' ')" = "main.pdf main.synctex.gz main.tex paper.env " ] \
  && ok "fast builds and clean paper folder" || fail "unexpected paper files"
cd "$root"

# Different papers build in parallel with independent engine settings.
bin/paper build "papers/$a/main.tex" >/dev/null 2>&1 & p1=$!
bin/paper build "papers/$b/main.tex" >"$logs/b.log" 2>&1 & p2=$!
bin/paper build "papers/$c/main.tex" >"$logs/c.log" 2>&1 & p3=$!
wait $p1 || fail "parallel pdflatex"
wait $p2 || { tail -20 "$logs/b.log"; fail "xelatex"; }
wait $p3 || { tail -20 "$logs/c.log"; fail "tectonic"; }
grep -q xelatex "$logs/b.log" && ok "parallel builds and engine overrides" || fail "xelatex not used"
[ -s "papers/$c/main.pdf" ] || fail "tectonic pdf"

# Autosave and an agent targeting one paper are serialized by its build lock.
bin/paper build "papers/$a/main.tex" >/dev/null 2>&1 & p1=$!
bin/paper build "papers/$a/main.tex" >/dev/null 2>&1 || fail "concurrent same paper"
wait $p1 && ok "per-document locking" || fail "concurrent same paper"

bin/paper build --journal "papers/$a/main.tex" >/dev/null 2>&1 && ok "journal build" || fail "journal build"
bin/paper fmt --help >/dev/null 2>&1 && ok "tool subcommands" || fail "fmt"
bin/paper doctor >/dev/null && ok "doctor and TeXpresso capabilities" || fail "doctor"

# Exercise the real TeXpresso-XeTeX engine against the container's TeX Live.
docker exec -e SDL_VIDEODRIVER=dummy -w "$root/papers/$a" paper-latex \
  texpresso -texlive -test-initialize main.tex >"$logs/texpresso.log" 2>&1 \
  && ok "TeXpresso TeX Live initialization" || { tail -20 "$logs/texpresso.log"; fail "TeXpresso"; }

# Isolation and path validation.
docker exec paper-latex test ! -e "$HOME/.ssh" && ok "host home not visible" || fail "home visible"
docker exec paper-latex touch /usr/x 2>/dev/null && fail "root fs writable" || ok "root fs read-only"
(cd /tmp && "$root/bin/paper" build x.tex >/dev/null 2>&1) && fail "outside project allowed" || ok "path isolation"
echo PASS
