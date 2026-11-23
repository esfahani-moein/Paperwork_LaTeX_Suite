# ---------------------------------------------------------------------------
# Author compilation image: selected TeX Live, standard engines, Tectonic,
# TeXpresso and formatting/lint tools. No editor runs here.
# ---------------------------------------------------------------------------
FROM debian:trixie-slim AS texpresso-runtime

# Extract the matched release bundle; checksums pin both architectures.
ARG TEXPRESSO_VERSION=2.0.1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip \
 && rm -rf /var/lib/apt/lists/*
RUN set -eu; arch=$(uname -m); \
    case "$arch" in \
      x86_64) target=linux-x64; sha=c867bf21b199faf9ddad440385c5fd38566782e62c9d58807545a882ec332d7f ;; \
      aarch64) target=linux-arm64; sha=802f3d1f8c6790ac9fa41257a8f353318639705c5bd9fa012a444c92ce0518c0 ;; \
      *) echo "unsupported TeXpresso architecture: $arch" >&2; exit 1 ;; \
    esac; \
    url="https://github.com/DominikPeters/texpresso-vscode/releases/download/v$TEXPRESSO_VERSION/texpresso-$target.vsix"; \
    curl -fsSL "$url" -o /tmp/texpresso.vsix; \
    echo "$sha  /tmp/texpresso.vsix" | sha256sum -c -; \
    unzip -q /tmp/texpresso.vsix "extension/runtime/$target/*" -d /tmp/runtime; \
    mkdir /opt/texpresso; \
    cp -R "/tmp/runtime/extension/runtime/$target/." /opt/texpresso/

FROM debian:trixie-slim

ARG SCHEME=scheme-full
ARG TEXLIVE=latest
ARG TEXFMT_VERSION=0.5.7
ARG TECTONIC_VERSION=0.17.0

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gpg perl git libfontconfig1 \
 && rm -rf /var/lib/apt/lists/*

# Install the requested annual snapshot, or the current release for TEXLIVE=latest.
RUN set -eu; \
    case "$TEXLIVE" in \
      latest) repo=https://mirror.ctan.org/systems/texlive/tlnet ;; \
      [0-9][0-9][0-9][0-9]) repo="https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/$TEXLIVE/tlnet-final" ;; \
      *) echo "TEXLIVE must be latest or a four-digit year" >&2; exit 1 ;; \
    esac; \
    mkdir /tmp/tl && cd /tmp/tl; \
    curl -fsSL "$repo/install-tl-unx.tar.gz" | tar -xz --strip-components=1; \
    perl install-tl --no-interaction --location "$repo" --scheme="$SCHEME" \
      --texdir=/usr/local/texlive --no-doc-install --no-src-install; \
    ln -s /usr/local/texlive/bin/*-linux /usr/local/texlive/bin/current; \
    rm -rf /tmp/tl /usr/local/texlive/install-tl.log

ENV PATH=/opt/texpresso/bin:/usr/local/texlive/bin/current:$PATH

# Smaller schemes still need the tools used by paper and the editor.
RUN tlmgr install latexmk chktex latexdiff texcount units placeins \
 && (luaotfload-tool -u || true)

RUN arch=$(uname -m) \
 && curl -fsSL "https://github.com/WGUNDERWOOD/tex-fmt/releases/download/v$TEXFMT_VERSION/tex-fmt-$arch-linux.tar.gz" \
    | tar -xz -C /usr/local/bin tex-fmt

RUN arch=$(uname -m) \
 && curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40$TECTONIC_VERSION/tectonic-$TECTONIC_VERSION-$arch-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin tectonic

COPY --from=texpresso-runtime /opt/texpresso /opt/texpresso

# Runtime is unprivileged and read-only; every writable cache is versioned.
RUN useradd -m -u 1000 -s /bin/bash writer \
 && mkdir -p /cache /build && chown writer:writer /cache /build
ARG BUILD_ID=dev
ENV PAPER_TEXLIVE=$TEXLIVE \
    PAPER_IMAGE_ID=$BUILD_ID \
    TEXMFVAR=/cache/texmf-var-$TEXLIVE-$BUILD_ID \
    TEXMFCONFIG=/cache/texmf-config-$TEXLIVE-$BUILD_ID \
    XDG_CACHE_HOME=/cache/xdg-$TEXLIVE-$BUILD_ID
USER writer

# Pre-fetch common Tectonic resources; normal TeX Live builds need no network.
RUN for c in article report; do for s in 10pt 11pt 12pt; do \
      printf '%s\n' "\\documentclass[$s]{$c}\\usepackage{amsmath,amssymb,graphicx,booktabs,hyperref}" \
        '\title{T}\author{A}\begin{document}\maketitle\section{S}\textbf{B} \emph{E} $x^2$\end{document}' > /tmp/w.tex \
      && tectonic --outdir /tmp /tmp/w.tex || exit 1; done; done; rm -f /tmp/w.*

WORKDIR /tmp
