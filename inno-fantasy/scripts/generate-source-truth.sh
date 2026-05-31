#!/usr/bin/env bash
set -euo pipefail

# VM/cron template for the post-match source-of-truth generation step.
#
# Required:
#   - Run after the day's matches are finished.
#   - Run from a VM/container where uv is installed.
#   - Set APISPORTS_KEY or API_FOOTBALL_KEY in the environment, or in backend/.env.
#
# Usage:
#   ./scripts/generate-source-truth.sh 2022-11-21
#
# Optional environment knobs:
#   FANTASY_CUP_MATCH_DATE=2022-11-21  # used when no date argument is passed
#   LEAGUE_ID=1                        # optional one-off override; default comes from backend/config/config.yaml
#   SEASON=2022                        # optional one-off override; default comes from backend/config/config.yaml
#   MATCHDAY_ID=wc-2022-20221121
#   REFRESH=1                          # force live API-Football calls instead of cache
#   ALLOW_INCOMPLETE=1                 # write an inspection file even if games are not FT/AET/PEN
#   IGNORE_PUBLIC_DATA=1               # resolve fixtures by API date instead of public matchday
#   FIXTURE_IDS=855735,855736          # explicit fixture ids, comma-separated
#
# Example cron:
#   0 23 * * * /opt/fantasy-cup/inno-fantasy/scripts/generate-source-truth.sh 2022-11-21 >> /var/log/inno-fantasy-source-truth.log 2>&1

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${APP_ROOT}/backend"

MATCH_DATE="${1:-${FANTASY_CUP_MATCH_DATE:-}}"
LEAGUE_ID="${LEAGUE_ID:-}"
SEASON="${SEASON:-}"

if [[ -z "${MATCH_DATE}" ]]; then
  echo "Missing match date. Pass YYYY-MM-DD or set FANTASY_CUP_MATCH_DATE." >&2
  echo "Example: ./scripts/generate-source-truth.sh 2022-11-21" >&2
  exit 2
fi

cmd=(
  uv run python -m services.daily_truth_gen
  --match-date "${MATCH_DATE}"
)

if [[ -n "${LEAGUE_ID}" ]]; then
  cmd+=(--league-id "${LEAGUE_ID}")
fi

if [[ -n "${SEASON}" ]]; then
  cmd+=(--season "${SEASON}")
fi

if [[ -n "${MATCHDAY_ID:-}" ]]; then
  cmd+=(--matchday-id "${MATCHDAY_ID}")
fi

if [[ "${REFRESH:-0}" == "1" ]]; then
  cmd+=(--refresh)
fi

if [[ "${ALLOW_INCOMPLETE:-0}" == "1" ]]; then
  cmd+=(--allow-incomplete)
fi

if [[ "${IGNORE_PUBLIC_DATA:-0}" == "1" ]]; then
  cmd+=(--ignore-public-data)
fi

if [[ -n "${FIXTURE_IDS:-}" ]]; then
  IFS="," read -r -a fixture_ids <<< "${FIXTURE_IDS}"
  for fixture_id in "${fixture_ids[@]}"; do
    trimmed="${fixture_id//[[:space:]]/}"
    if [[ -n "${trimmed}" ]]; then
      cmd+=(--fixture-id "${trimmed}")
    fi
  done
fi

cd "${BACKEND_DIR}"

echo "[source-truth] generating match_date=${MATCH_DATE} league_id=${LEAGUE_ID:-config.yaml} season=${SEASON:-config.yaml}"
"${cmd[@]}"
echo "[source-truth] written to ${APP_ROOT}/data/source_of_truth"
