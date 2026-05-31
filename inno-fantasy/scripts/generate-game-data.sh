#!/usr/bin/env bash
set -euo pipefail

# Single entrypoint for generating JSON data used by the game.
#
# Usage:
#   bash scripts/generate-game-data.sh public 2022-11-21
#   bash scripts/generate-game-data.sh truth 2022-11-21
#   bash scripts/generate-game-data.sh all 2022-11-21
#
# public: morning public bundle consumed by uploaded skills.
# truth: post-match source-of-truth bundle consumed by scoring.
# all:    runs public first, then truth. Useful for local historical simulation.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

MODE="${1:-}"
MATCH_DATE="${2:-${FANTASY_CUP_MATCH_DATE:-${FANTASY_CUP_AS_OF_DATE:-}}}"

usage() {
  echo "Usage: bash scripts/generate-game-data.sh public|truth|all YYYY-MM-DD" >&2
  echo "Examples:" >&2
  echo "  bash scripts/generate-game-data.sh public 2022-11-21" >&2
  echo "  bash scripts/generate-game-data.sh truth 2022-11-21" >&2
  exit 2
}

if [[ -z "${MODE}" || -z "${MATCH_DATE}" ]]; then
  usage
fi

case "${MODE}" in
  public)
    bash "${SCRIPT_DIR}/generate-public-data.sh" "${MATCH_DATE}"
    ;;
  truth)
    bash "${SCRIPT_DIR}/generate-source-truth.sh" "${MATCH_DATE}"
    ;;
  all)
    bash "${SCRIPT_DIR}/generate-public-data.sh" "${MATCH_DATE}"
    bash "${SCRIPT_DIR}/generate-source-truth.sh" "${MATCH_DATE}"
    ;;
  *)
    usage
    ;;
esac
