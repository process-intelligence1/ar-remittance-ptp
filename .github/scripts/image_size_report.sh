#!/usr/bin/env bash
# Build the API image from a backend folder (NOT pushed anywhere) and print where its size goes.
#   bash .github/scripts/image_size_report.sh <backend folder> <label>
# Compressed sizes = each layer gzipped, which is close to what the registry stores.
set -euo pipefail
ctx="$1"; label="$2"; tag="size-report:$(echo "$label" | tr -c 'a-z0-9' '-')"
out="${GITHUB_STEP_SUMMARY:-/dev/stdout}"
mb() { awk -v b="$1" 'BEGIN { printf "%.1f", b / 1048576 }'; }

docker build -q -t "$tag" "$ctx" > /dev/null
work=$(mktemp -d); docker save "$tag" -o "$work/img.tar"; tar -xf "$work/img.tar" -C "$work"

# layer files in order (docker save manifest), their gzipped size, and the Dockerfile step that made them
mapfile -t layers < <(jq -r '.[0].Layers[]' "$work/manifest.json")
mapfile -t steps < <(docker history --no-trunc --format '{{.Size}}|{{.CreatedBy}}' "$tag" | tac | awk -F'|' '$1 != "0B"')
total=0; rows=""
for i in "${!layers[@]}"; do
  gz=$(gzip -c "$work/${layers[$i]}" | wc -c); total=$((total + gz))
  raw=$(stat -c %s "$work/${layers[$i]}")
  step=$(echo "${steps[$i]:-?|?}" | cut -d'|' -f2- | sed 's/^\/bin\/sh -c //; s/#(nop) *//' | cut -c1-110 | tr '|' '/')
  rows="$rows| $((i + 1)) | $(mb "$gz") | $(mb "$raw") | \`$step\` |\n"
done

inside() { docker run --rm --entrypoint sh "$tag" -c "$1" 2>/dev/null || true; }
{
  echo "## Image size report: $label"
  echo ""
  echo "**Total: $(mb "$total") MB compressed** ($(mb "$(stat -c %s "$work/img.tar")") MB unpacked)"
  echo ""
  echo "| Layer | Compressed MB | Unpacked MB | Made by |"
  echo "|---|---|---|---|"
  printf "$rows"
  echo ""
  echo "<details><summary>Largest Python packages (unpacked MB)</summary>"
  echo ""; echo '```'
  inside 'du -sm /opt/venv/lib/python3.12/site-packages/* /opt/py/*/* 2>/dev/null | sort -rn | head -25'
  echo '```'; echo "</details>"; echo ""
  echo "<details><summary>Largest system libraries, Tesseract data, other folders (unpacked MB)</summary>"
  echo ""; echo '```'
  inside 'du -sm /usr/lib/x86_64-linux-gnu/* 2>/dev/null | sort -rn | head -20; echo ---;
          du -sm /usr/share/tesseract-ocr/*/tessdata/* 2>/dev/null | sort -rn | head -12; echo ---;
          du -sm /usr/local/lib/python3.12 /usr/share/doc /usr/share/man /usr/share/locale /usr/share/zoneinfo /var/lib/dpkg /opt/venv /opt/py /srv 2>/dev/null'
  echo '```'; echo "</details>"; echo ""
  echo "<details><summary>pip / build tools / caches left in the image</summary>"
  echo ""; echo '```'
  inside 'ls -d /opt/venv/lib/python3.12/site-packages/pip* /opt/venv/lib/python3.12/site-packages/setuptools* \
            /opt/venv/lib/python3.12/site-packages/wheel* /root/.cache /home/appuser/.cache 2>/dev/null;
          command -v gcc cc make strip 2>/dev/null; echo "(end)"'
  echo '```'; echo "</details>"; echo ""
} >> "$out"
rm -rf "$work"
