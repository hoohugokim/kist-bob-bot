#!/usr/bin/env bash
# =============================================================================
# notify_dooray.sh — send a Dooray channel notification via Incoming Hook.
#
# Transport: incoming webhook only (posts as the channel's bot; rings/pushes).
# The hook URL *is* the credential — anyone holding it can post to the
# channel. Keep it in dooray.conf (chmod 600), never in the repo.
#
# Usage:
#   notify_dooray.sh "<title>" "[detail]" "[color]" "[attachments_json]"
#
# attach_json (optional): a JSON array of hook attachment objects, e.g.
# [{"text":"K1 …","color":"blue","imageUrl":"https://…"}]
#   — posted as-is via the hook (both "image" and "imageUrl" render).
#
# Config (dooray.conf next to this script, chmod 600):
#   DOORAY_HOOK_URL=...          # incoming webhook URL (required)
#   DOORAY_BOT_NAME=KIST-Bob-Bot # bot name shown in channel
#
# Bot avatar:
#   DOORAY_BOT_ICON_URL=https://…  public image URL used as the bot icon on
#   every post (hook field botIconImage). Empty = Dooray's default icon.
#
# Dev/test overrides (all optional, env-driven):
#   KBB_DRY_RUN=1        build the exact hook payload, print + save it, POST nothing
#                        (dry-run payloads land in .dryrun/)
#   KBB_LOCAL_CONF=path  use a different project-local conf instead of dooray.conf
#                        (e.g. dooray.sandbox.conf → a personal test channel)
#
# Never echoes the hook URL.
set -uo pipefail

TITLE="${1:?usage: notify_dooray.sh <text> [detail] [color] [attach_json]}"
DETAIL="${2:-}"
COLOR="${3:-blue}"
ATTACH="${4:-}"
BOT="${DOORAY_BOT_NAME:-KIST-Bob-Bot}"

# Project-local config (hook + bot identity).
# KBB_LOCAL_CONF redirects to an alternate conf (sandbox/test channel).
LOCAL_CFG="${KBB_LOCAL_CONF:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dooray.conf}"
case "$LOCAL_CFG" in
  /*) : ;;
  *) LOCAL_CFG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$LOCAL_CFG" ;;
esac
[ -r "$LOCAL_CFG" ] && . "$LOCAL_CFG"

# Build the hook payload (also used by dry-run).
PAYLOAD=$(python3 -c '
import json,sys
bot,text,detail,color,attach,icon = sys.argv[1:7]
p = {"botName": bot, "text": text}
if icon:
    p["botIconImage"] = icon
if attach:
    try:
        a = json.loads(attach)
        if not isinstance(a, list):
            raise ValueError
        p["attachments"] = a
    except ValueError:
        print("notify_dooray: attach_json is not a JSON array; posting text only", file=sys.stderr)
elif detail:
    p["attachments"] = [{"text": detail, "color": color}]
print(json.dumps(p, ensure_ascii=False))
' "$BOT" "$TITLE" "$DETAIL" "$COLOR" "$ATTACH" "${DOORAY_BOT_ICON_URL:-}")

if [ "${KBB_DRY_RUN:-0}" = "1" ]; then
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.dryrun"
  mkdir -p "$DIR"
  FILE="$DIR/$(date +%Y%m%d-%H%M%S)-$$.json"
  echo "$PAYLOAD" | python3 -m json.tool > "$FILE" 2>/dev/null || cp <(echo "$PAYLOAD") "$FILE"
  echo "notify_dooray: DRY RUN — nothing posted. payload saved to $FILE"
  echo "$PAYLOAD"
  exit 0
fi

if [ -z "${DOORAY_HOOK_URL:-}" ]; then
  echo "notify_dooray: no Dooray target configured. Set DOORAY_HOOK_URL in $LOCAL_CFG" >&2
  exit 2
fi

code=$(curl -s -o /dev/null -w '%{http_code}' -m 15 -X POST \
    -H 'Content-Type: application/json' -d "$PAYLOAD" "$DOORAY_HOOK_URL")
[ "$code" = "200" ] && exit 0
echo "notify_dooray: hook POST returned $code" >&2; exit 1
