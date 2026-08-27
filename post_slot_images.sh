#!/usr/bin/env bash
# =============================================================================
# post_slot_images.sh — follow-up post with the meal photos, once the
# cafeteria has uploaded them. Photos are entered manually on the service
# day (observed: lunch 11:04–11:18, dinner 17:30–17:43), i.e. AFTER the
# 11:00/17:00 menu post — so images travel in a separate card.
#
# Usage: post_slot_images.sh <lunch|dinner> [--date YYYYMMDD]
#
# Behavior:
#   - no photos registered for the slot yet  → silent exit 0
#   - photos exist and not yet posted today  → post image card, write state
#   - photos already posted today            → silent exit 0
# Cron-friendly: run every few minutes inside the lunch/dinner windows.
# =============================================================================
set -uo pipefail

# The state-file date key is KIST's local date, regardless of host timezone.
export TZ=Asia/Seoul

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRAPER="$SCRIPT_DIR/kist_menu_scraper.py"
NOTIFY="$SCRIPT_DIR/notify_dooray.sh"
# KBB_STATE_DIR isolates test runs from the production once-per-day state.
STATE_DIR="${KBB_STATE_DIR:-$SCRIPT_DIR/.state}"

SLOT="${1:?usage: post_slot_images.sh <lunch|dinner> [--date YYYYMMDD]}"
case "$SLOT" in lunch|dinner) ;; *) echo "slot must be lunch|dinner" >&2; exit 2 ;; esac

DATE_ARG=""
DATE_SET=""
for a in "$@"; do
  if [ -n "$DATE_SET" ]; then DATE_ARG="--date=$a"; DATE_SET=""; continue; fi
  case "$a" in
    --date=*) DATE_ARG="--date=${a#--date=}" ;;
    --date)   DATE_SET=1 ;;
  esac
done

MENU_JSON=$(python3 "$SCRAPER" --slot "$SLOT" $DATE_ARG 2>/dev/null) || exit 0
[ -z "$MENU_JSON" ] && exit 0

# Build the photo card. Prints: "READY <yyyymmdd>\n<title>\n<attachments JSON>" or "NOTREADY".
# Attachments use the hook's `imageUrl` field, which the gov instance renders inline.
BUILT=$(python3 - "$MENU_JSON" "$SLOT" "$SCRIPT_DIR" << 'PY'
import json, sys

menu = json.loads(sys.argv[1])
slot = sys.argv[2]

slots = menu.get("slots") or []
if menu.get("closed") or not slots:
    print("NOTREADY")
    sys.exit(0)
s = slots[0]
with_imgs = [m for m in s["items"] if m.get("imgThumb") or m.get("img")]
if not with_imgs:
    print("NOTREADY")
    sys.exit(0)

sys.path.insert(0, sys.argv[3])
from kist_menu_scraper import _iso_date, _fmt_n

date = menu.get("date", "????????")
yoil = menu.get("yoil", "")
word = {"lunch": "Lunch", "dinner": "Dinner"}[slot]
title = f"📷 KIST Cafeteria {word} Photos — {_iso_date(date)} ({yoil})"
att = []
for m in with_imgs:
    url = m.get("imgThumb") or m.get("img")
    cap = m["menuNm"]
    kcal, prot = m.get("kcal"), m.get("protein")
    bits = []
    if kcal is not None: bits.append(_fmt_n(kcal, "kcal"))
    if prot is not None: bits.append("Protein " + _fmt_n(prot, "g"))
    if bits:
        cap += f" — {' · '.join(bits)}"
    if m.get("corner"):
        cap = f"{m['corner']} {cap}"
    att.append({"text": cap, "color": "blue", "imageUrl": url})
print(f"READY {date}")
print(title)
print(json.dumps(att, ensure_ascii=False))
PY
)

[ "$(echo "$BUILT" | head -1 | cut -d' ' -f1)" = "READY" ] || exit 0
DATE_KEY=$(echo "$BUILT" | head -1 | cut -d' ' -f2)
TITLE=$(echo "$BUILT" | sed -n '2p')
ATTACH=$(echo "$BUILT" | sed -n '3p')

mkdir -p "$STATE_DIR"
# drop state older than 7 days
find "$STATE_DIR" -name '????????-*' -mtime +7 -delete 2>/dev/null

STATE_FILE="$STATE_DIR/${DATE_KEY}-${SLOT}"
[ -f "$STATE_FILE" ] && exit 0   # already posted for this date+slot

"$NOTIFY" "$TITLE" "" "blue" "$ATTACH" || exit 1
if [ "${KBB_DRY_RUN:-0}" = 1 ]; then
  echo "post_slot_images: DRY RUN — $SLOT photos for $DATE_KEY (state not written)"
else
  echo "posted $(date '+%F %T')" > "$STATE_FILE"
  echo "post_slot_images: posted $SLOT photos for $DATE_KEY"
fi