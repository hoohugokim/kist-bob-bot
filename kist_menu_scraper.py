#!/usr/bin/env python3
"""
KIST-Bob-Bot -- scrape KIST cafeteria menu from Pulmuone's "원더풀 플러스".

Full browser-equivalent flow (reverse-engineered):
  1. POST /src/sql/intro/intro_sql.php  requestId=search_storeList  -> all restaurants
  2. Find the target row (KIST_TARGET_NAME), extract raw operCd/assignCd
  3. POST /src/sql/intro/intro_sql.php  requestId=search_pageStore -> short DB codes
  4. POST /src/sql/menu/today_sql.php  requestId=search_schMenu  (short codes + date)
  5. Per corner: POST /src/sql/menu/nutrient_sql.php  requestId=search_menuDetail
  6. Emit JSON on stdout; kist_bob_bot.sh formats it, notify_dooray.sh posts it
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

PULM_BASE = os.environ.get("PULM_BASE", "https://puls2.pulmuone.com")
TARGET_NAME = os.environ.get("KIST_TARGET_NAME", "KIST")

args = None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _post(url: str, form_dict: dict) -> Optional[dict]:
    """POST form-encoded data, return JSON dict or None.
    Pauses 1 s after each request to keep the load on the public API light."""
    try:
        data = urllib.parse.urlencode(form_dict).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json,text/html",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            if not raw:
                return None
            result = json.loads(raw)
    except Exception as e:
        if args and args.debug:
            print(f"  POST error: {e}", file=sys.stderr)
        return None
    time.sleep(1)
    return result


# ---------------------------------------------------------------------------
# Step 1: find KIST in store list
# ---------------------------------------------------------------------------

def find_kist_codes() -> Optional[Dict[str, str]]:
    """Return {operCd, assignCd, assignNm, assignGrp} for the target store
    (KIST_TARGET_NAME substring match), or None."""
    url = f"{PULM_BASE}/src/sql/intro/intro_sql.php"
    payload = {
        "requestId": "search_storeList",
        "requestUrl": "/src/sql/intro/intro_sql.php",
        "requestMode": "1",
        "requestParam": "{}",
    }
    data = _post(url, payload)
    if not data:
        return None
    for row in data.get("storeList", []):
        name = row[2] if len(row) > 2 else ""
        if TARGET_NAME in name:
            return {
                "operCd": row[0],
                "assignCd": row[1],
                "assignNm": name,
                "assignGrp": row[3] if len(row) > 3 else "",
            }
    return None


# ---------------------------------------------------------------------------
# Step 2: search_pageStore — transform codes
# ---------------------------------------------------------------------------

def transform_codes(raw_oper: str, raw_assign: str) -> Optional[Dict[str, str]]:
    """Call search_pageStore to get short DB codes.
    Returns {operCd, assignCd, assignNm, assignGrp} or None."""
    url = f"{PULM_BASE}/src/sql/intro/intro_sql.php"
    payload = {
        "requestId": "search_pageStore",
        "requestUrl": "/src/sql/intro/intro_sql.php",
        "requestMode": "1",
        "requestParam": json.dumps({
            "operCd": raw_oper,
            "assignCd": raw_assign,
        }),
    }
    data = _post(url, payload)
    if not data:
        return None
    row = (data.get("storeList") or [None])[0]
    if not row:
        return None
    return {
        "operCd": row[0] or "",
        "assignCd": row[1] or "",
        "assignNm": row[2] or "",
        "assignGrp": row[3] or "",
    }


# ---------------------------------------------------------------------------
# Step 3: query today's menu
# ---------------------------------------------------------------------------

def yoil_kr(d: str) -> str:
    try:
        y, m, day = int(d[:4]), int(d[4:6]), int(d[6:8])
        days = ["월", "화", "수", "목", "금", "토", "일"]
        return days[date(y, m, day).weekday()]
    except Exception:
        return ""


def _num(v: Any) -> Optional[float]:
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else f


def query_nutrient_detail(short_oper: str, short_assign: str, date_str: str,
                          time_cd: str, shop_cd: str) -> Dict[str, dict]:
    """Per-corner nutrient detail (nutrient_sql.php / search_menuDetail).
    time_cd/shop_cd are the per-row codes c9/c8 (NOT the appTimeCd corner name).
    Returns {menuNm: {kcal, sodium, carbs, protein, fat, ratio, components}}
    for that corner's mains. ratio = "carbs:protein:fat" energy %, components =
    [(subNm, subKcal), ...] (sums to the meal kcal)."""
    url = f"{PULM_BASE}/src/sql/menu/nutrient_sql.php"
    payload = {
        "requestId": "search_menuDetail",
        "requestUrl": "/src/sql/menu/nutrient_sql.php",
        "requestMode": "1",
        "requestParam": json.dumps({
            "srchOperCd": short_oper,
            "srchAssignCd": short_assign,
            "srchMenuDay": date_str,
            "srchTimeCd": time_cd,
            "srchShopCd": shop_cd,
        }),
    }
    data = _post(url, payload)
    out: Dict[str, dict] = {}
    for row in (data or {}).get("data") or []:
        # row: [menuNm, kcal, sodiumMg, carbsG, proteinG, fatG, ratio, subNm, subKcal]
        if not isinstance(row, list) or len(row) < 6 or not row[0]:
            continue
        nm = row[0]
        d = out.get(nm)
        if d is None:
            d = out[nm] = {
                "kcal": _num(row[1]),
                "sodium": _num(row[2]),
                "carbs": _num(row[3]),
                "protein": _num(row[4]),
                "fat": _num(row[5]),
                "ratio": row[6] if len(row) > 6 else None,
                "components": [],
            }
        # one row per component (macros repeat; subNm/subKcal differ)
        if len(row) > 8 and row[7]:
            d["components"].append((row[7], _num(row[8])))
    return out


def query_today_menu(short_oper: str, short_assign: str,
                     date_str: str, slot: str = "all") -> dict:
    """Query menu for a given date using short DB codes.
    slot: 'all' | '010'/'breakfast' | '020'/'lunch' | '030'/'dinner'
    Returns dict with: date, yoil, slots(list), closed(bool), error(str|None)."""
    result: dict = {
        "date": date_str,
        "yoil": yoil_kr(date_str),
        "slots": [],
        "closed": False,
        "error": None,
    }

    url = f"{PULM_BASE}/src/sql/menu/today_sql.php"

    # First get time slot names (search_schNm)
    sch_nm_payload = {
        "requestId": "search_schNm",
        "requestUrl": "/src/sql/menu/today_sql.php",
        "requestMode": "1",
        "requestParam": json.dumps({
            "srchOperCd": short_oper,
            "srchAssignCd": short_assign,
            "srchCurDay": date_str,
        }),
    }
    sch_nm_data = _post(url, sch_nm_payload)

    # Then get menu (search_schMenu)
    menu_payload = {
        "requestId": "search_schMenu",
        "requestUrl": "/src/sql/menu/today_sql.php",
        "requestMode": "1",
        "requestParam": json.dumps({
            "srchOperCd": short_oper,
            "srchAssignCd": short_assign,
            "srchCurDay": date_str,
            "srchCurShopclsCd": "",
            "custCd": "",
        }),
    }
    menu_data = _post(url, menu_payload)

    if not menu_data:
        result["error"] = "menu endpoint returned no data"
        return result

    result["closed"] = menu_data.get("closeGb") == "1"
    if result["closed"]:
        result["error"] = "cafeteria closed today"
        return result

    raw_data = menu_data.get("data")
    if not raw_data:
        result["error"] = "no menu data available"
        return result

    # Map time codes to names from schNm result
    time_map: Dict[str, str] = {}
    if sch_nm_data:
        cds = sch_nm_data.get("schTimeCd", [])
        nms = sch_nm_data.get("schTimeNm", [])
        for cd, nm in zip(cds, nms):
            time_map[cd] = nm

    # Row indices per /src/js/menu/today.js (fn_searchView):
    # [0]=appTimeCd(010/020/030) [1]=menuNm [2]=kcal [3]=imgPath [4]=imgNm
    # [5]=bigo(부메뉴) [6]=cornerNm(K1/K2/...) [8]=shopCd [9]=timeCd
    # [13]=thumbnailNm [17]=mealCost [21]=nutrientGb
    # NOTE: [2] is Kcal (the web UI shows it as "Kcal"); [17] is the price and
    # is -1/0 (free) for KIST. Image upload timestamp is embedded in [4]
    # (e.g. 002_001_20260821110433_0.jpg = uploaded 11:04:33).
    SLOT_ALIASES = {"breakfast": "010", "lunch": "020", "dinner": "030"}
    want = SLOT_ALIASES.get(slot, slot)

    items_by_time: Dict[str, List[dict]] = {}
    for row in raw_data:
        if not isinstance(row, list) or len(row) < 10:
            continue
        time_cd0 = row[0]
        if want != "all" and time_cd0 != want:
            continue
        menu_nm = row[1] or ""
        if not menu_nm:
            continue
        img_path = row[3] if len(row) > 3 else ""
        img_nm = row[4] if len(row) > 4 else ""
        thm_nm = row[13] if len(row) > 13 else ""
        img = ""
        thm = ""
        if img_path and img_nm:
            base = img_path if img_path.startswith("http") \
                else "https://did2.drimhitech.com" + img_path
            img = base + img_nm
            if thm_nm:
                thm = base + thm_nm
        item = {
            "menuNm": menu_nm,
            "kcal": _num(row[2]),
            "ingredients": row[5] or "",
            "corner": row[6] or "",
            "shopCd": row[8] or "",
            "rowTimeCd": row[9] or "",
            "protein": None,
            "img": img,
            "imgThumb": thm,
        }
        items_by_time.setdefault(time_cd0, []).append(item)

    # Enrich with per-corner nutrient detail (authoritative kcal + protein).
    for menus in items_by_time.values():
        queried = set()
        for it in menus:
            key = (it["rowTimeCd"], it["shopCd"])
            if not all(key) or key in queried:
                continue
            queried.add(key)
            detail = query_nutrient_detail(short_oper, short_assign,
                                           date_str, *key)
            for m2 in menus:
                if (m2["rowTimeCd"], m2["shopCd"]) == key and m2["menuNm"] in detail:
                    d = detail[m2["menuNm"]]
                    m2["kcal"] = d["kcal"] if d["kcal"] is not None else m2["kcal"]
                    m2["protein"] = d["protein"]
                    m2["sodium"] = d["sodium"]
                    m2["carbs"] = d["carbs"]
                    m2["fat"] = d["fat"]
                    m2["ratio"] = d["ratio"]
                    m2["components"] = d["components"]

    # Group by time slot with per-slot totals
    for time_cd in sorted(items_by_time):
        menus = items_by_time[time_cd]
        total_kcal = sum(m["kcal"] for m in menus
                         if isinstance(m["kcal"], (int, float)))
        total_protein = sum(m["protein"] for m in menus
                            if isinstance(m["protein"], (int, float)))
        result["slots"].append({
            "timeCd": time_cd,
            "timeNm": time_map.get(time_cd, time_cd),
            "totalKcal": total_kcal or None,
            "totalProtein": total_protein or None,
"items": [{k: m[k] for k in ("menuNm", "corner", "kcal",
                                          "protein", "sodium", "carbs",
                                          "fat", "ratio", "components",
                                          "ingredients", "img", "imgThumb",
                                          "rowTimeCd", "shopCd")}
                      for m in menus],
        })

    return result


# ---------------------------------------------------------------------------
# Format for Dooray
# ---------------------------------------------------------------------------

def _fmt_n(v: Any, unit: str) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and not v.is_integer():
        return f"{v:g} {unit}"
    return f"{v:,} {unit}" if isinstance(v, int) and v >= 1000 else f"{v} {unit}"


def _iso_date(d: Any) -> str:
    """'yyyymmdd' -> 'yyyy-mm-dd' (ISO 8601); other values pass through."""
    if isinstance(d, str) and len(d) == 8 and d.isdigit():
        return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    return str(d or "")


def format_dooray_text(menu_result: dict, slot_word: str = "") -> tuple:
    """Return (title, body, color) for the Dooray notification."""
    date_str = menu_result.get("date", "????????")
    yoil = menu_result.get("yoil", "")
    title = f"🏫 KIST Cafeteria{' ' + slot_word if slot_word else ''} — {_iso_date(date_str)} ({yoil})"

    if menu_result.get("closed"):
        return title, "⚠️ 오늘도 식당 휴무입니다.", "gray"

    slots = menu_result.get("slots", [])
    if not slots:
        body = "ℹ️ 오늘의 메뉴 정보가 등록되지 않았습니다."
        if menu_result.get("error"):
            body += f"\n   ({menu_result['error']})"
        return title, body, "yellow"

    lines = []
    for slot in slots:
        lines.append(f"▸ {slot['timeNm']}")
        for m in slot["items"]:
            corner = f" [{m['corner']}]" if m.get("corner") else ""
            kcal = _fmt_n(m.get("kcal"), "kcal")
            protein = _fmt_n(m.get("protein"), "g")
            tail_parts = []
            if kcal:
                tail_parts.append(kcal)
            if protein:
                tail_parts.append(f"protein {protein}")
            parts = [f"  · {m['menuNm']}{corner}"]
            if tail_parts:
                parts.append(" — " + " / ".join(tail_parts))
            lines.append("".join(parts))
    return title, "\n".join(lines), "green"


def _bar(pct: int, width: int = 10) -> str:
    """TUI bar: 10 blocks = 100% (2% per block). ■/□ render at uniform
    width on macOS/iOS (unlike █/░); Windows/Android to be confirmed."""
    filled = max(0, min(width, int(round(pct * width / 100))))
    return "■" * filled + "□" * (width - filled)


def format_nutrient_detail_text(menu_result: dict) -> str:
    """ASCII 'detail page' card: macro bars + sodium + component Kcal.

    Plain text (no code fence): Dooray clients render fences inconsistently
    (stray backticks / red text). Macro rows use single CJK labels
    (탄/단/지 = carbs/protein/fat) so the label column is uniform-width on
    every platform; single spaces only (markdown collapses repeats).
    The %→grams gap is an en space (U+2002), which markdown does not
    collapse — plain repeated spaces would render as one. The dish line
    (corner + name) is bold; the kcal/sodium part sits on its own line
    under it (no em dash); macro gram weights are whole grams — so lines
    stay short on narrow mobile screens.
    Returns '' if no nutrient detail is registered for any item.
    """
    slots = menu_result.get("slots", [])
    if not slots:
        return ""
    blocks = []  # (header, [row, ...], parts_line or None)
    for slot in slots:
        for m in slot["items"]:
            nm = m['menuNm']
            if m.get("corner"):
                nm = f"{m['corner']} {nm}"
            head = f"**{nm}**"
            bits = [_fmt_n(m.get("kcal"), "kcal")]
            if m.get("sodium") is not None:
                bits.append(f"sodium {_fmt_n(m['sodium'], 'mg')}")
            if bits:
                head += "\n" + " · ".join(b for b in bits if b)
            blocks.append((head, [], None))
            if not (m.get("carbs") is not None or m.get("ratio")):
                continue
            pcts = ("", "", "")
            if m.get("ratio"):
                vals = str(m["ratio"]).split(":")
                if len(vals) >= 3:
                    pcts = tuple(vals[:3])
            rows = []
            for kor, val, pct in zip(("탄", "단", "지"),
                                     (m.get("carbs"), m.get("protein"), m.get("fat")),
                                     pcts):
                if val is None:
                    continue
                try:
                    p = int(float(pct)) if pct and pct != "null" else 0
                except ValueError:
                    p = 0
                # "\u2002": en space — a real visual gap that survives markdown's
                # repeated-space collapsing (plain spaces render as one)
                # whole grams: decimal weights pushed the 탄 line past the
                # width on Android
                rows.append(f"{kor} {_bar(p)} {p} % \u2002{_fmt_n(int(round(float(val))), 'g')}")
            parts = None
            comps = [c for c in (m.get("components") or []) if c[1] is not None]
            if comps:
                comps.sort(key=lambda x: -x[1])
                names = " · ".join(f"{nm} {int(kcal)}" if float(kcal).is_integer()
                                   else f"{nm} {kcal:g}" for nm, kcal in comps)
                parts = names
            blocks[-1] = (blocks[-1][0], rows, parts)
    if not any(b[1] or b[2] for b in blocks):
        return ""
    lines = []
    for head, rows, parts in blocks:
        lines.append("")
        lines.append(head)
        lines.extend(rows)
        if parts:
            lines.append(parts)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global args
    import argparse
    ap = argparse.ArgumentParser(
        description="Scrape KIST cafeteria lunch menu from Pulmuone")
    ap.add_argument("--date", default=None,
                    help="Date as YYYYMMDD (default: today)")
    ap.add_argument("--slot", default="all",
                    choices=["all", "breakfast", "lunch", "dinner"],
                    help="Time slot to include (default: all)")
    ap.add_argument("--debug", action="store_true",
                    help="Print debug info to stderr")
    args = ap.parse_args()

    date_str = args.date or date.today().strftime("%Y%m%d")
    if len(date_str) != 8:
        print(f"invalid date: {date_str}", file=sys.stderr)
        sys.exit(1)

    if args.debug:
        print(f"target date: {date_str} ({yoil_kr(date_str)})", file=sys.stderr)

    # Step 1: find KIST
    kist = find_kist_codes()
    if not kist:
        out = {"date": date_str, "yoil": yoil_kr(date_str),
               "slots": [], "closed": False,
               "error": "could not find KIST in store list"}
        print(json.dumps(out, ensure_ascii=False))
        sys.exit(1)

    if args.debug:
        print(f"found KIST: {kist['assignNm']}", file=sys.stderr)
        print(f"  raw operCd: {kist['operCd']}", file=sys.stderr)
        print(f"  raw assignCd: {kist['assignCd']}", file=sys.stderr)

    # Step 2: transform codes
    transformed = transform_codes(kist["operCd"], kist["assignCd"])
    if not transformed:
        out = {"date": date_str, "yoil": yoil_kr(date_str),
               "slots": [], "closed": False,
               "error": "search_pageStore returned no data"}
        print(json.dumps(out, ensure_ascii=False))
        sys.exit(1)

    if args.debug:
        print(f"  short operCd: {transformed['operCd']}", file=sys.stderr)
        print(f"  short assignCd: {transformed['assignCd']}", file=sys.stderr)

    # Step 3: query menu
    menu = query_today_menu(transformed["operCd"],
                            transformed["assignCd"], date_str, slot=args.slot)

    if args.debug:
        print(f"menu: closed={menu.get('closed')}, "
              f"slots={[(s['timeNm'], len(s['items'])) for s in menu.get('slots', [])]}",
              file=sys.stderr)

    print(json.dumps(menu, ensure_ascii=False))


if __name__ == "__main__":
    main()
