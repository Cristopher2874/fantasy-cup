#!/usr/bin/env bash
set -euo pipefail

# VM/cron template for the morning public-data generation step.
#
# Required:
#   - Run from a VM/container where uv is installed.
#   - Set APISPORTS_KEY or API_FOOTBALL_KEY in the environment, or in backend/.env.
#
# Usage:
#   ./scripts/generate-public-data.sh 2022-11-21
#
# Optional environment knobs:
#   FANTASY_CUP_AS_OF_DATE=2022-11-21  # used when no date argument is passed
#   LEAGUE_ID=1
#   SEASON=2022
#   REFRESH=1                          # force live API-Football calls instead of cache
#
# Example cron:
#   0 6 * * * /opt/fantasy-cup/inno-fantasy/scripts/generate-public-data.sh 2022-11-21 >> /var/log/inno-fantasy-public-data.log 2>&1

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${APP_ROOT}/backend"

AS_OF_DATE="${1:-${FANTASY_CUP_AS_OF_DATE:-}}"
LEAGUE_ID="${LEAGUE_ID:-1}"
SEASON="${SEASON:-2022}"

if [[ -z "${AS_OF_DATE}" ]]; then
  echo "Missing as-of date. Pass YYYY-MM-DD or set FANTASY_CUP_AS_OF_DATE." >&2
  echo "Example: ./scripts/generate-public-data.sh 2022-11-21" >&2
  exit 2
fi

cmd=(
  uv run python -m services.daily_source_gen
  --as-of-date "${AS_OF_DATE}"
  --league-id "${LEAGUE_ID}"
  --season "${SEASON}"
)

if [[ "${REFRESH:-0}" == "1" ]]; then
  cmd+=(--refresh)
fi

cd "${BACKEND_DIR}"

echo "[public-data] generating as_of_date=${AS_OF_DATE} league_id=${LEAGUE_ID} season=${SEASON}"
"${cmd[@]}"
echo "[public-data] written to ${APP_ROOT}/data/public_data"
