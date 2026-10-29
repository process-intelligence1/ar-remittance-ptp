#!/usr/bin/env bash
# Print (to the job summary) the compressed size of the image just built and the GHCR storage of one package.
#   bash .github/scripts/ghcr_report.sh <package: ar-api | ar-worker>      (needs docker login, GH_TOKEN, GITHUB_SHA)
set -uo pipefail
pkg="${1:?package name}"
owner="${GITHUB_REPOSITORY_OWNER}"
IMAGE="ghcr.io/$owner/$pkg"
# compressed sizes as stored in the registry. A version is either an image manifest (config + layers) or an
# image index (older builds with attestations) -> add its children. A child of an old index may already be
# deleted (it was its own "version"): count it as 0.
image_size() {
  local raw
  if ! raw=$(docker buildx imagetools inspect --raw "$IMAGE@$1" 2>/dev/null); then
    echo "missing ${1:7:12}" >> "missing-$pkg.txt"; echo 0; return
  fi
  if echo "$raw" | jq -e '.manifests' > /dev/null; then
    local s=0 c n
    for c in $(echo "$raw" | jq -r '.manifests[].digest'); do n=$(image_size "$c"); s=$((s + n)); done
    echo "$s"
  else
    echo "$raw" | jq -r '.layers[]? | "\(.digest) \(.size)"' >> "layers-$pkg.txt"
    echo "$raw" | jq '[.config.size // 0] + [.layers[]?.size] | add'
  fi
}
digests=$(gh api "/users/$owner/packages/container/$pkg/versions" --paginate --jq '.[].name')
: > "layers-$pkg.txt"; : > "missing-$pkg.txt"; total=0; summary=""
for d in $digests; do
  size=$(image_size "$d")
  tags=$(gh api "/users/$owner/packages/container/$pkg/versions" --paginate \
         --jq ".[] | select(.name==\"$d\") | .metadata.container.tags | join(\",\")")
  total=$((total + size))
  summary="$summary| ${tags:-untagged} | ${d:7:12} | $((size / 1048576)) MB |\n"
done
unique=$(sort -u "layers-$pkg.txt" | awk '{s+=$2} END {print s+0}')
current=$(image_size "$(docker buildx imagetools inspect "$IMAGE:${GITHUB_SHA}" --format '{{json .Manifest}}' | jq -r .digest)")
{
  echo "### $pkg - this image (${GITHUB_SHA:0:7}): **$((current / 1048576)) MB** compressed"
  echo ""
  echo "GHCR storage of $pkg (public package: storage is free; 3 newest versions + running kept)"
  echo ""
  echo "| Tags | Digest | Size |"
  echo "|---|---|---|"
  printf "$summary"
  echo ""
  echo "Versions kept: $(echo "$digests" | wc -w). Storage used: **$((unique / 1048576)) MB** (shared layers counted once);"
  echo "upper bound if every version is counted in full: $((total / 1048576)) MB."
  if [ -s "missing-$pkg.txt" ]; then
    echo ""
    echo "Parts of older image indexes already deleted (counted as 0): $(sort -u "missing-$pkg.txt" | wc -l)"
  fi
} >> "$GITHUB_STEP_SUMMARY"
