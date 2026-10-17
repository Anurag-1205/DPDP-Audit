#!/usr/bin/env bash
# Build the PoliCheck / PolicyLint Docker image from the authors' repository.
# The 2020 Dockerfile runs apt-get on Debian buster, whose mirrors are archived,
# so those two lines are dropped (the Python base image already has what it needs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPO="$ROOT/data/external/PrivacyPolicyAnalysis"

if [ ! -d "$REPO" ]; then
  git clone --depth 1 https://github.com/benandow/PrivacyPolicyAnalysis.git "$REPO"
fi
cd "$REPO/DockerImage"
sed -i -e '/^RUN apt-get update/d' -e '/^RUN apt-get upgrade/d' Dockerfile
# The 852 MB spaCy model downloads very slowly inside the build; if it was fetched on the
# host first (data/external/models/), install it from the local file instead.
LG="$ROOT/data/external/models/en_core_web_lg-2.0.0.tar.gz"
if [ -f "$LG" ] && grep -q "spacy download en_core_web_lg" Dockerfile; then
  cp "$LG" .
  sed -i 's#^RUN python -m spacy download en_core_web_lg#COPY en_core_web_lg-2.0.0.tar.gz /tmp/\nRUN pip install --no-cache-dir /tmp/en_core_web_lg-2.0.0.tar.gz \&\& python -m spacy link en_core_web_lg en_core_web_lg --force#' Dockerfile
fi
docker build -t benandow/pol-analysis .

# Pretrained NLP model used by PoliCheck (Google Drive, from the authors' README).
if [ ! -e "$REPO/ext/NlpFinalModel" ]; then
  "$ROOT/.venv/bin/pip" install -q gdown
  "$ROOT/.venv/bin/gdown" 1yMB3TJt8oZX3-GHm9oB_eKU7oeJXfLbA -O "$REPO/ext/NlpFinalModel.download"
  tar xzf "$REPO/ext/NlpFinalModel.download" -C "$REPO/ext"
  rm "$REPO/ext/NlpFinalModel.download"
fi
