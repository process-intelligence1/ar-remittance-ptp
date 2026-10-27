#!/usr/bin/env bash
# Print a gitleaks JSON report as a table WITHOUT secret values (rule, file, commit, line).
#   bash .github/scripts/leaks_summary.sh <report.json> <label>
set -euo pipefail
report="$1"; label="$2"
n=$(jq 'length' "$report" 2>/dev/null || echo 0)
{
  echo "### gitleaks: $label - $n finding(s)"
  if [ "$n" -gt 0 ]; then
    echo ""
    echo "| Rule | File | Commit | Line |"
    echo "|---|---|---|---|"
    jq -r '.[] | "| \(.RuleID) | \(.File) | \((.Commit // "")[0:7]) | \(.StartLine) |"' "$report" | sort -u
  fi
  echo ""
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
