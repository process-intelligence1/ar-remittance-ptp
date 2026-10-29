#!/usr/bin/env bash
# Delete old versions of one image package in GHCR: keep the N newest AND every image the Azure resources run
# (env RUNNING = space-separated image references from the deploy job, e.g. ghcr.io/owner/ar-api:<sha>
# ghcr.io/owner/ar-worker:<sha>). If RUNNING is empty (unknown), nothing is deleted.
#   bash .github/scripts/ghcr_cleanup.sh <package: ar-api | ar-worker> <N>
set -euo pipefail
pkg="${1:?package name}"
keep="${2:-3}"
owner="${GITHUB_REPOSITORY_OWNER}"
api="users/$owner/packages/container/$pkg/versions"

if [ -z "${RUNNING// /}" ]; then
  echo "::warning::Could not tell which images Azure runs - nothing deleted this time ($pkg)."
  exit 0
fi
# tags of the running images that belong to THIS package
running_tags=$(for img in $RUNNING; do case "$img" in *"/$pkg:"*) echo "${img##*:}" ;; esac; done)
echo "[$pkg] running image tag(s): ${running_tags:-none}"

# newest first: id, tags
gh api "$api" --paginate --jq 'sort_by(.created_at) | reverse | .[] | "\(.id) \(.metadata.container.tags | join(","))"' > "versions-$pkg.txt"
n=0
while read -r id tags; do
  n=$((n + 1))
  is_running=false
  for t in $running_tags; do
    case ",$tags," in *",$t,"*) is_running=true ;; esac
  done
  if [ "$n" -le "$keep" ] || [ "$is_running" = true ]; then
    echo "keep   $id ${tags:-untagged}$([ "$is_running" = true ] && echo ' (running)')"
  else
    echo "delete $id ${tags:-untagged}"
    gh api -X DELETE "users/$owner/packages/container/$pkg/versions/$id" > /dev/null
  fi
done < "versions-$pkg.txt"
