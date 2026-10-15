#!/usr/bin/env bash
# Download and unpack OPP-115 (99 MB) into data/raw/OPP-115.
# The server throttles single connections, so the file is fetched in 12 byte ranges.
set -euo pipefail
cd "$(dirname "$0")/../data/raw" 2>/dev/null || { mkdir -p "$(dirname "$0")/../data/raw"; cd "$(dirname "$0")/../data/raw"; }
URL=https://usableprivacy.org/static/data/OPP-115_v1_0.zip
TOTAL=$(curl -sI "$URL" | awk 'tolower($1)=="content-length:" {print $2}' | tr -d '\r')
N=12; CHUNK=$(( (TOTAL + N - 1) / N )); mkdir -p parts
for i in $(seq 0 $((N-1))); do
  s=$(( i*CHUNK )); e=$(( s + CHUNK - 1 )); [ $e -ge $TOTAL ] && e=$((TOTAL-1))
  curl -s -r "$s-$e" -o "parts/p$(printf %02d $i)" "$URL" &
done
wait
cat parts/p* > OPP-115_v1_0.zip && rm -rf parts
unzip -tq OPP-115_v1_0.zip && unzip -q -o OPP-115_v1_0.zip -x "__MACOSX/*"
echo "OPP-115 ready in data/raw/OPP-115"
