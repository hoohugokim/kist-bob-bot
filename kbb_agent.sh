#!/usr/bin/env bash
# =============================================================================
# kbb_agent.sh — KIST-Bob-Bot scheduler daemon (systemd user service).
#
#   * on start:       posts "🟢 KIST-Bob-Bot online"
#   * Mon–Fri:        lunch menu post 11:00–11:59 (retries while the
#                     cafeteria hasn't registered it; gives up at 11:55),
#                     dinner menu post 17:00–17:59 (gives up at 17:55)
#                     photo watcher every 5 min: 11:05–11:55 / 17:05–18:25
#   * on SIGTERM/SIGINT: posts "🔴 KIST-Bob-Bot offline" FIRST, then exits
#
# A meal whose whole window was missed (machine was off) is not posted late.
#
# KBB_LIFECYCLE_NOTICE=0 suppresses the 🟢/🔴 notices — set it in the systemd
# unit (Environment=...) on machines that reboot often during the work day.
# =============================================================================
set -uo pipefail

# Schedule windows and date keys follow KIST's local time, regardless of
# the host's timezone.
export TZ=Asia/Seoul

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
# KBB_STATE_DIR isolates test runs from the production once-per-day state.
STATE_DIR="${KBB_STATE_DIR:-$SCRIPT_DIR/.state}"
mkdir -p "$STATE_DIR"

BOT="$SCRIPT_DIR/kist_bob_bot.sh"
NOTIFY="$SCRIPT_DIR/notify_dooray.sh"
PHOTOS="$SCRIPT_DIR/post_slot_images.sh"
SCRAPER="$SCRIPT_DIR/kist_menu_scraper.py"

log() { printf 'kbb_agent: %s\n' "$*"; }

post_online() {
  if [ "${KBB_LIFECYCLE_NOTICE:-1}" = "0" ]; then
    log "online notice suppressed (KBB_LIFECYCLE_NOTICE=0)"
    return 0
  fi
  if "$NOTIFY" "🟢 KIST-Bob-Bot online" \
       "Mon–Fri: lunch 11:00 · dinner 17:00 + photo follow-ups." "green"; then
    log "posted online"
  else
    log "ERROR: online notice failed"
  fi
}

SHUTTING_DOWN=0
post_offline_and_exit() {
  [ "$SHUTTING_DOWN" = 1 ] && exit 0
  SHUTTING_DOWN=1
  trap - TERM INT
  if [ "${KBB_LIFECYCLE_NOTICE:-1}" = "0" ]; then
    log "stopping — offline notice suppressed (KBB_LIFECYCLE_NOTICE=0)"
    exit 0
  fi
  log "stopping — posting offline notice"
  if "$NOTIFY" "🔴 KIST-Bob-Bot offline" \
       "Bot is now offline, no posts until it is back online." "red"; then
    log "posted offline"
  else
    log "ERROR: offline notice failed"
  fi
  exit 0
}
trap post_offline_and_exit TERM INT

# prune state older than 7 days (same policy as post_slot_images.sh)
find "$STATE_DIR" -name '????????-*' -mtime +7 -delete 2>/dev/null

log "starting (pid $$)"
post_online

# try_menu <slot> <window_start_min> <giveup_min> <now_min>
# Posts the slot's menu once per day. While the cafeteria hasn't registered
# it (orchestrator exit 3), retries every tick; at giveup, posts a yellow
# warning once instead of a menu. The warning is based on a final read-only
# probe, so it tells the truth: menu unregistered / bot missed the window
# (menu exists) / cafeteria closed / menu service unreachable.
try_menu() {
  local slot=$1 wstart=$2 giveup=$3 now=$4 rc
  local day state missed probe probe_rc verdict detail
  day=$(date +%Y%m%d)
  state="$STATE_DIR/${day}-${slot}-menu"
  missed="$STATE_DIR/${day}-${slot}-menu-missed"
  if [ -f "$state" ] || [ -f "$missed" ]; then return 0; fi
  if [ "$now" -lt "$wstart" ]; then return 0; fi
  if [ "$now" -ge "$giveup" ]; then
    # Final read-only probe so the warning reports the real cause instead
    # of always blaming the cafeteria (the bot may have simply been down,
    # or the network/endpoint may be unreachable). Exit 1 = lookup/network/
    # endpoint failure; exit 0 = service answered (menu may simply be absent).
    probe=$(python3 "$SCRAPER" --slot "$slot" --date "$day" 2>/dev/null)
    probe_rc=$?
    if [ "$probe_rc" -ne 0 ] || [ -z "$probe" ]; then
      verdict="unreachable"
    else
      verdict=$(python3 -c '
import json, sys
d = json.loads(sys.argv[1])
if d.get("closed"):
    print("closed")
elif any(s.get("items") for s in (d.get("slots") or [])):
    print("registered")
else:
    print("unregistered")
' "$probe" 2>/dev/null)
    fi
    case "$verdict" in
      registered)
        detail="as of $(date +%H:%M) the ${slot} menu WAS registered, but the bot was offline for the post window — nothing was posted for this meal" ;;
      closed)
        detail="as of $(date +%H:%M) the cafeteria is closed today — no ${slot} menu to post" ;;
      unregistered)
        detail="as of $(date +%H:%M) the cafeteria had not registered today's ${slot} menu — nothing was posted for this meal" ;;
      *)
        detail="as of $(date +%H:%M) the bot could not reach the menu service (network down or endpoint change?) — nothing was posted for this meal" ;;
    esac
    if "$NOTIFY" "⚠️ ${slot} menu not posted" "$detail" "yellow"; then
      [ "${KBB_DRY_RUN:-0}" = 1 ] || echo "$(date '+%F %T')" > "$missed"
    fi
    return 0
  fi
  rc=0
  "$BOT" "$slot" || rc=$?
  case "$rc" in
    0)
      if [ "${KBB_DRY_RUN:-0}" = 1 ]; then
        log "$slot menu DRY-RUN ok (state not written)"
      else
        echo "$(date '+%F %T')" > "$state"; log "$slot menu posted"
      fi ;;
    3) log "$slot menu not registered yet — retrying" ;;
    *) log "$slot menu post failed (rc=$rc) — retrying" ;;
  esac
}

while :; do
  dow=$(date +%u)
  if [ "$dow" -le 5 ]; then
    h=$(date +%H); m=$(date +%M)
    min=$((10#$h * 60 + 10#$m))
    try_menu lunch  660  715  "$min"   # 11:00–11:55
    try_menu dinner 1020 1075 "$min"   # 17:00–17:55
    if [ $((min % 5)) -eq 0 ]; then
      [ "$min" -ge 665 ]  && [ "$min" -lt 720 ]  && "$PHOTOS" lunch   # 11:05–11:55
      [ "$min" -ge 1025 ] && [ "$min" -le 1109 ] && "$PHOTOS" dinner  # 17:05–18:25
    fi
  fi
  sleep 30
done