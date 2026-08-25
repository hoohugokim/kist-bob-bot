#!/usr/bin/env bash
# =============================================================================
# kist-bob-bot — daily KIST cafeteria menu → Dooray channel notification.
#
# Flow:
#   1. python3 kist_menu_scraper.py --slot <slot> [--date YYYYMMDD] → JSON on stdout
#   2. Format a pretty Dooray message (title / body / color) from the JSON
#   3. notify_dooray.sh <title> <body> <color>  → push to Dooray
#
# Usage:
#   kist_bob_bot.sh [lunch|dinner|all] [--date YYYYMMDD]
#     lunch  — 중식 (default schedule: 11:00)
#     dinner — 석식 (default schedule: 17:00)
#     all    — every posted slot (manual testing)
#
# Scheduling (cron example — the orchestrator is idempotent per day via .state/):
#   * 11-12 * * 1-5  cd /path/to/kist-bob-bot && ./kist_bob_bot.sh lunch
#   * 17-18 * * 1-5  cd /path/to/kist-bob-bot && ./kist_bob_bot.sh dinner
#
# Exit codes:
#   0 — notification sent successfully (or already posted today — skipped)
#   1 — scraping or notification failed
#   2 — no Dooray target configured
#   3 — menu not registered yet (NOTHING posted; kbb_agent.sh retries)
# =============================================================================
set -uo pipefail

# The state-file date key is KIST's local date, regardless of host timezone.
export TZ=Asia/Seoul

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRAPER="$SCRIPT_DIR/kist_menu_scraper.py"
NOTIFY="$SCRIPT_DIR/notify_dooray.sh"

SLOT="all"
DATE_ARG=""
for a in "$@"; do
  case "$a" in
    lunch|dinner|all) SLOT="$a" ;;
    --date=*)         DATE_ARG="--date=${a#--date=}" ;;
    --date)           : ;; # handled via $2 below
  esac
done
# --date VALUE form
prev=""
for a in "$@"; do
  if [ "$prev" = "--date" ]; then DATE_ARG="--date=$a"; fi
  prev="$a"
done

die() { echo "kist-bob-bot: $*" >&2; exit 1; }

# ---- 0. Once-per-day guard (safe under every-minute cron) -------------------
# Same state file the agent writes, so a manual/cron post also suppresses the
# agent's (and vice versa). 'all' is manual-only and stays unguarded.
STATE_DIR="${KBB_STATE_DIR:-$SCRIPT_DIR/.state}"
STATE_FILE=""
if [ "$SLOT" != "all" ]; then
  DAY_KEY=$(date +%Y%m%d)
  [ -n "$DATE_ARG" ] && DAY_KEY="${DATE_ARG#--date=}"
  STATE_FILE="$STATE_DIR/${DAY_KEY}-${SLOT}-menu"
  if [ -f "$STATE_FILE" ]; then
    echo "kist-bob-bot: ${DAY_KEY} ${SLOT} menu already posted — skipping"
    exit 0
  fi
fi

# ---- 1. Scrape the menu ----------------------------------------------------
MENU_JSON=$(python3 "$SCRAPER" --slot "$SLOT" $DATE_ARG)
if [ $? -ne 0 ] || [ -z "$MENU_JSON" ]; then
  die "menu scraper failed or returned empty"
fi

# ---- 2. Parse and format the notification ----------------------------------
FORMATTED=$(python3 - "$MENU_JSON" "$SLOT" "$SCRIPT_DIR" << 'PY'
import json, sys

menu = json.loads(sys.argv[1])
slot = sys.argv[2]
sys.path.insert(0, sys.argv[3])
from kist_menu_scraper import format_dooray_text

slot_word = {"lunch": "Lunch", "dinner": "Dinner"}.get(slot, "")
title, body, color = format_dooray_text(menu, slot_word)
print(f"{title}\n{body}\n{color}")
PY
)

if [ -z "$FORMATTED" ]; then
  die "failed to format notification"
fi

# Split: last line = color, first line = title, rest = body
COLOR_LINE=$(echo "$FORMATTED" | tail -1)
TITLE_BODY=$(echo "$FORMATTED" | sed '$d')
TITLE=$(echo "$TITLE_BODY" | head -1)
BODY=$(echo "$TITLE_BODY" | tail -n +2)

# Nutrient detail card (ASCII macro bars + component Kcal); '' if unregistered.
DETAIL_TEXT=$(python3 - "$MENU_JSON" "$SCRIPT_DIR" << 'PY'
import json, sys
menu = json.loads(sys.argv[1])
sys.path.insert(0, sys.argv[2])
from kist_menu_scraper import format_nutrient_detail_text
print(format_nutrient_detail_text(menu))
PY
)

# ---- 3. Notify Dooray ------------------------------------------------------
# "yellow" = menu not registered yet — post nothing; let the caller retry.
if [ "$COLOR_LINE" = "yellow" ]; then
  echo "kist-bob-bot: menu not registered yet (exit 3, nothing posted)" >&2
  exit 3
fi
# Nutrition detail: plain-text post (title + detail in the main message;
# no attachment card). The plain menu list is redundant with it.
if [ -n "$DETAIL_TEXT" ]; then
  "$NOTIFY" "$TITLE"$'\n'"$DETAIL_TEXT" "" ""
else
  # No nutrient detail registered — fall back to the plain menu list card.
  "$NOTIFY" "$TITLE" "$BODY" "$COLOR_LINE"
fi
rc=$?
# Record success (dry-run writes no state) — the once-per-day guard reads it.
if [ "$rc" -eq 0 ] && [ -n "$STATE_FILE" ] && [ "${KBB_DRY_RUN:-0}" != "1" ]; then
  mkdir -p "$STATE_DIR"
  echo "$(date '+%F %T')" > "$STATE_FILE"
fi
exit "$rc"