#!/bin/sh
# ---------------------------------------------------------------------------
# test.sh: end-to-end self-check of the whole setup, run from the Mac like VS Code/agents do.
# Usage: ./test.sh [scheme]     e.g. ./test.sh scheme-small  (faster image build for testing)
# Creates papers/_test_* temporarily and removes them at the end.
# ---------------------------------------------------------------------------
set -eu
cd "$(dirname "$0")"; root=$(pwd -P)
[ -n "${1:-}" ] && export TEXLIVE_SCHEME="$1"         # shell env overrides paper.env for compose
trap 'rm -rf "$root"/papers/_test_*' EXIT
now() { perl -MTime::HiRes=time -e 'printf "%.3f", time'; }
ok() { echo "ok   $*"; }
fail() { echo "FAIL $*"; exit 1; }

PAPER_ROOT=$root docker compose --env-file paper.env build -q && bin/paper up >/dev/null 2>&1

bin/paper new _test_a >/dev/null && bin/paper new _test_b >/dev/null && bin/paper new _test_c >/dev/null
echo ENGINE=xelatex  > papers/_test_b/paper.env
echo ENGINE=tectonic > papers/_test_c/paper.env

# 1. Build from the paper folder (how LaTeX Workshop calls it), first = dumps preamble, second = cached.
cd papers/_test_a
bin=../../bin
$bin/paperbuild main.tex >/tmp/paper_a.log 2>&1 || { tail -20 /tmp/paper_a.log; fail "first build"; }
sed -i '' 's/Start writing/Keep writing/' main.tex
s=$(now); $bin/paperbuild main.tex >/dev/null 2>&1 || fail "rebuild"; e=$(now)
ok "rebuild via shim: $(echo "$e - $s" | bc)s"
s=$(now); docker exec -w "$PWD" paper-latex paperbuild main.tex >/dev/null 2>&1; e=$(now)
ok "rebuild direct (no shim): $(echo "$e - $s" | bc)s"
[ "$(ls | sort | tr '\n' ' ')" = "main.pdf main.synctex.gz main.tex paper.env " ] && ok "no clutter in paper folder" || fail "clutter: $(ls)"
cd "$root"

# 2. Parallel builds of different papers (agent style: from project root) + engine overrides.
bin/paperbuild papers/_test_a/main.tex >/dev/null 2>&1 & p1=$!
bin/paperbuild papers/_test_b/main.tex >/tmp/paper_b.log 2>&1 & p2=$!
bin/paperbuild papers/_test_c/main.tex >/tmp/paper_c.log 2>&1 & p3=$!
wait $p1 || fail "parallel a"; wait $p2 || { tail -20 /tmp/paper_b.log; fail "xelatex"; }; wait $p3 || { tail -20 /tmp/paper_c.log; fail "tectonic"; }
grep -q xelatex /tmp/paper_b.log && ok "xelatex override (parallel)" || fail "xelatex not used"
[ -s papers/_test_c/main.pdf ] && ok "tectonic override (parallel)" || fail "tectonic pdf"

# 3. Same paper twice at once (autosave + agent): the lock serializes, both succeed.
bin/paperbuild papers/_test_a/main.tex >/dev/null 2>&1 & p1=$!
bin/paperbuild papers/_test_a/main.tex >/dev/null 2>&1 || fail "concurrent same paper"
wait $p1 && ok "concurrent builds of one paper" || fail "concurrent same paper"

# 4. Journal build, tools, and isolation/hardening.
bin/paperbuild --journal papers/_test_a/main.tex >/dev/null 2>&1 && ok "journal build" || fail "journal build"
bin/tex-fmt --help >/dev/null 2>&1 && ok "tex-fmt shim" || fail "tex-fmt"
docker exec paper-latex test ! -e "$HOME/.ssh" && ok "host home not visible" || fail "home visible"
docker exec paper-latex touch /usr/x 2>/dev/null && fail "root fs writable" || ok "root fs read-only"
(cd /tmp && "$root/bin/paperbuild" x.tex 2>/dev/null) && fail "outside project allowed" || ok "refuses files outside project"
echo PASS
