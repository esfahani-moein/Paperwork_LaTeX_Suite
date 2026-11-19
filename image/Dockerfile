# ---------------------------------------------------------------------------
# Paper LaTeX compile image.
# What it is: a headless compile service (no editor inside). VS Code and AI
# agents run on the host and call into it through bin/paper (docker exec).
# Contents: Debian 13 "trixie" (current stable) + TeX Live (latest, or a frozen
# year via the CTAN arg) + Tectonic + tex-fmt + paperbuild.
# Built by compose.yaml; settings come from paper.env.
# ---------------------------------------------------------------------------
FROM debian:trixie-slim

# SCHEME: TeX Live size (scheme-full = every package; writers never hit "missing package").
# CTAN:   package repository; a historic tlnet-final URL gives a frozen TeX Live year.
ARG SCHEME=scheme-full
ARG TEXFMT_VERSION=0.5.7
ARG TECTONIC_VERSION=0.17.0
ARG CTAN=https://mirror.ctan.org/systems/texlive/tlnet

# Minimal OS packages: TLS certs, downloader, gpg (TeX Live signature check), perl (latexmk/tlmgr),
# git, libfontconfig1 (XeTeX links against it).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gpg perl git libfontconfig1 \
 && rm -rf /var/lib/apt/lists/*

# TeX Live without docs/sources, installed to a year-independent path.
# install-tl verifies package checksums (and repository signature via gpg).
RUN mkdir /tmp/tl && cd /tmp/tl \
 && curl -fsSL "$CTAN/install-tl-unx.tar.gz" | tar -xz --strip-components=1 \
 && perl install-tl --no-interaction --location "$CTAN" --scheme="$SCHEME" \
      --texdir=/usr/local/texlive --no-doc-install --no-src-install \
 && ln -s /usr/local/texlive/bin/*-linux /usr/local/texlive/bin/current \
 && rm -rf /tmp/tl /usr/local/texlive/install-tl.log
ENV PATH=/usr/local/texlive/bin/current:$PATH

# Tools paperbuild relies on (already in scheme-full; needed for smaller schemes).
# Pre-build the system LuaTeX font cache so the first lualatex run is not slow.
RUN tlmgr install latexmk mylatexformat chktex \
 && (luaotfload-tool -u || true)

# tex-fmt: fast LaTeX formatter (Rust), static binary for this CPU.
RUN arch=$(uname -m) \
 && curl -fsSL "https://github.com/WGUNDERWOOD/tex-fmt/releases/download/v$TEXFMT_VERSION/tex-fmt-$arch-linux.tar.gz" \
    | tar -xz -C /usr/local/bin tex-fmt

# Tectonic: self-contained XeTeX-based engine (Rust), static musl binary for this CPU.
RUN arch=$(uname -m) \
 && curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40$TECTONIC_VERSION/tectonic-$TECTONIC_VERSION-$arch-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin tectonic

# Non-root user. /cache becomes a named volume (Docker seeds it from the image on first use),
# /build is a RAM disk at runtime. Root filesystem is read-only at runtime, so every
# writable cache is redirected into /cache.
RUN useradd -m -u 1000 -s /bin/bash writer \
 && mkdir -p /cache /build && chown writer:writer /cache /build
ENV TEXMFVAR=/cache/texmf-var XDG_CACHE_HOME=/cache/xdg
USER writer

# Pre-fetch Tectonic's common classes/sizes/fonts/packages into /cache: first builds are quick
# and typical papers also work with NETWORK=none. Anything else is downloaded on demand.
RUN for c in article report; do for s in 10pt 11pt 12pt; do \
      printf '%s\n' "\\documentclass[$s]{$c}\\usepackage{amsmath,amssymb,graphicx,booktabs,hyperref}" \
        '\title{T}\author{A}\begin{document}\maketitle\section{S}\textbf{b} \emph{e} $x^2$\end{document}' > /tmp/w.tex \
      && tectonic --outdir /tmp /tmp/w.tex || exit 1; done; done; rm -f /tmp/w.*

# Last layer so editing paperbuild does not invalidate the big layers above.
COPY --chmod=755 paperbuild /usr/local/bin/paperbuild
WORKDIR /tmp
