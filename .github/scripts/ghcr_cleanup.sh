#!/usr/bin/env bash
# Delete old versions of the ar-api image in GHCR: keep the N newest AND every image the Container App
# is running (env RUNNING = space-separated image references from the deploy job, e.g.
# ghcr.io/owner/ar-api:<sha>). If RUNNING is empty (unknown), nothing is deleted.
#   bash .github/scripts/ghcr_cleanup.sh <N>
set -euo pipefail
keep="${1:-3}"
owner="${GITHUB_REPOSITORY_OWNER}"
api="users/$owner/packages/container/ar-api/versions"

if [ -z "${RUNNING// /}" ]; then
  echo "::warning::Could not tell which image the Container App runs - nothing deleted this time."
  exit 0
fi
running_tags=$(for img in $RUNNING; do echo "${img##*:}"; done)
echo "Running image tag(s): $running_tags"

# newest first: id, tags
gh api "$api" --paginate --jq 'sort_by(.created_at) | reverse | .[] | "\(.id) \(.metadata.container.tags | join(","))"' > versions.txt
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
    gh api -X DELETE "users/$owner/packages/container/ar-api/versions/$id" > /dev/null
  fi
done < versions.txt
