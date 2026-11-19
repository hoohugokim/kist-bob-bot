# =============================================================================
# kbb_common.sh — shared helpers for kbb_agent.sh / kist_bob_bot.sh /
# post_slot_images.sh. Sourced, never executed.
# =============================================================================

# skip_dates.txt — dates the bot stays totally silent (menu + photos), like a
# weekend. Not a secret; safe to commit. KBB_SKIP_DATES_FILE redirects to an
# alternate file (tests). The agent re-reads it every tick — edits take effect
# without a restart.
KBB_SKIP_FILE="${KBB_SKIP_DATES_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skip_dates.txt}"

# is_skip_day <date> — true if the date is listed in the skip file.
# Accepts YYYYMMDD or YYYY-MM-DD (anything with 8 digits); '#' comments and
# blank lines in the file are ignored.
is_skip_day() {
  local d=${1//[!0-9]/}
  [ ${#d} -eq 8 ] || return 1
  [ -f "$KBB_SKIP_FILE" ] || return 1
  local d_dash="${d:0:4}-${d:4:2}-${d:6:2}"
  grep -Eq "^[[:space:]]*(${d}|${d_dash})[[:space:]]*(#.*)?$" "$KBB_SKIP_FILE"
}