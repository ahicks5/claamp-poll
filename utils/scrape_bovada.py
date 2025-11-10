# utils/scrape_bovada.py
# Bovada scraper: events + live scores + key markets (ML/Spread/Total), FULL-GAME only.

from __future__ import annotations

import json, time, random, re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import requests
import pandas as pd

__all__ = [
    "fetch_events_for_sport",
    "fetch_event_node_by_link",
    "extract_key_markets",
    "fetch_scores",
    "fetch_bovada_live_games_with_markets",
]

# =========================
# Config
# =========================

COUPON_BASE   = "https://www.bovada.lv/services/sports/event/coupon/events/A/description/"
COUPON_PARAMS = "?marketFilterId=def&preMatchOnly=false&eventsLimit=5000&lang=en"  # include live + prematch; you can filter later
DETAIL_BASE   = "https://www.bovada.lv/services/sports/event/coupon/events/A/description"
SCORES_BASE   = "https://services.bovada.lv/services/sports/results/api/v2/scores/"

REQ_TIMEOUT   = 12
RETRIES       = 3
SLEEP_BETWEEN = 0.25   # mild throttle between dependent requests

DEBUG = False  # flip to True if you want payload previews

# =========================
# Full-game filtering helpers
# =========================

WANTED_KEYS = {"2W-12", "3W-12", "2W-HCAP", "HCAP", "2W-OU", "OU"}

# Substrings that flag non–full-game markets
_BAD_PERIOD_TOKENS = (
    "1st half", "first half", "2nd half", "second half",
    "half", "quarter", "q1", "q2", "q3", "q4",
    "period 1", "period 2", "period 3", "period 4",
)
_BAD_MARKET_DESC_TOKENS = (
    "1st half", "2nd half", "quarter", "race to",
    "team total", "alternate", "alt", "winning margin",
    "exact score", "correct score",
)

def _is_full_game_period(period: dict | None) -> bool:
    """
    Heuristic gate:
      - Reject anything that looks like Half/Quarter by description/abbr/number.
      - Accept explicit 'Live Game'.
      - Accept 'Game' when period.main=True (Bovada sometimes uses this while live).
    """
    if not isinstance(period, dict):
        return False
    desc = (period.get("description") or "").strip().lower()
    abbr = (period.get("abbreviation") or "").strip().lower()
    num  = period.get("number") or period.get("periodNumber")

    hay = f"{desc} {abbr}".strip().lower()
    if any(tok in hay for tok in _BAD_PERIOD_TOKENS):
        return False
    if isinstance(num, int) and num in (1, 2, 3, 4):
        return False

    if "live" in desc and "game" in desc:
        return True
    if desc == "game" and bool(period.get("main", False)):
        return True
    if abbr in {"lg"}:
        return True

    return False

def _allowed_market_desc(desc: str | None) -> bool:
    d = (desc or "").strip().lower()
    if any(tok in d for tok in _BAD_MARKET_DESC_TOKENS):
        return False
    return any(tok in d for tok in ("moneyline", "point spread", "spread", "total"))

def _norm_minus(s: Optional[str]) -> Optional[str]:
    return None if s is None else s.replace("−", "-")

def _to_num(val: Optional[str]) -> Optional[float]:
    if val is None: return None
    try:
        return float(val)
    except Exception:
        return None

def _to_int(val: Optional[str]) -> Optional[int]:
    if val is None: return None
    try:
        return int(str(val).strip())
    except Exception:
        return None

def _safe_dt_ms(ms: Optional[int]) -> Optional[datetime]:
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except Exception:
        return None

# =========================
# HTTP helpers
# =========================

def _ua() -> Dict[str, str]:
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    return {
        "User-Agent": random.choice(agents),
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
    }

def http_get(url: str) -> Optional[requests.Response]:
    last_err = None
    for i in range(RETRIES):
        try:
            resp = requests.get(url, headers=_ua(), timeout=REQ_TIMEOUT)
            return resp
        except requests.RequestException as e:
            last_err = e
            time.sleep(0.3 + 0.4 * i)
    if DEBUG:
        print(f"[WARN] GET failed after {RETRIES} tries: {url} :: {last_err}")
    return None

def http_get_json(url: str) -> Optional[Any]:
    resp = http_get(url)
    if resp is None:
        return None
    if resp.status_code == 404:
        return None
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        if DEBUG:
            print(f"[DEBUG] HTTP {resp.status_code} for {url}")
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        if DEBUG:
            print(f"[DEBUG] JSON decode error for {url}; text[:200]={resp.text[:200]}")
        return None

# =========================
# Coupon (events) layer
# =========================

def fetch_events_for_sport(sport_path: str, live_only: bool = True) -> pd.DataFrame:
    """
    Coupon API → return events for a single sport.
    - live_only=True: only live games
    - live_only=False: include prematch too
    """
    url = f"{COUPON_BASE}{sport_path}{COUPON_PARAMS}"
    block = http_get_json(url)
    if not block:
        return pd.DataFrame()

    try:
        sport_desc = block[0]["path"][0]["description"]
    except Exception:
        sport_desc = None

    rows = []
    for ev in block[0].get("events", []):
        is_live = bool(ev.get("live", False))
        if live_only and not is_live:
            continue

        comps = ev.get("competitors") or []
        home = next((c for c in comps if c.get("home")), {})
        away = next((c for c in comps if not c.get("home")), {})

        rows.append({
            "sport": sport_desc,
            "event_id": ev.get("id"),
            "description": ev.get("description"),
            "link": ev.get("link"),
            "start_time_utc": _safe_dt_ms(ev.get("startTime")),
            "status": ev.get("status"),
            "last_modified_utc": _safe_dt_ms(ev.get("lastModified")),
            "home_team": home.get("name"),
            "away_team": away.get("name"),
            "home_competitor_id": str(home.get("id") or home.get("competitorId") or ""),
            "away_competitor_id": str(away.get("id") or away.get("competitorId") or ""),
            "is_live": is_live,
        })
    return pd.DataFrame(rows)

# =========================
# Markets layer (per event)
# =========================

DETAIL_KEY_MAP = {
    "moneyline": {"2W-12", "3W-12"},
    "spread":    {"2W-HCAP", "HCAP"},
    "total":     {"2W-OU", "OU"},
}

def fetch_event_node_by_link(link_path: str) -> Optional[Dict[str, Any]]:
    url = f"{DETAIL_BASE}{link_path}?lang=en"
    js = http_get_json(url)
    if not js:
        return None
    try:
        return (js[0].get("events") or [None])[0]
    except Exception:
        return None

def extract_key_markets(ev_node, home_id, away_id, home_name, away_name):
    """
    ML/Spread/Total @ FULL GAME only, with per-market fallback:
      Live(Open) → Live(Susp) → Game(Open) → Game(Susp)
    Returns *_source in {"live","prematch"} so UI can tag 'Prematch fill'.
    """
    out = {
        "home_ml": None, "away_ml": None, "ml_status": None, "ml_source": None,
        "home_spread": None, "home_spread_price": None, "spread_status": None, "spread_source": None,
        "away_spread": None, "away_spread_price": None,
        "total_line": None, "over_price": None, "under_price": None, "total_status": None, "total_source": None,
    }
    if not ev_node:
        return out

    # collect candidates
    cands = []
    for dg in (ev_node.get("displayGroups") or []):
        dg_default = bool(dg.get("defaultType"))
        for m in (dg.get("markets") or []):
            key = m.get("key")
            if key not in WANTED_KEYS:
                continue
            period = m.get("period") or {}
            if not _is_full_game_period(period):
                continue
            if not _allowed_market_desc(m.get("description")):
                continue

            pdesc = (period.get("description") or "").strip()
            dkey  = (m.get("descriptionKey") or "")
            is_main_dynamic = dkey.lower().startswith("main dynamic")
            status = (m.get("status") or "").upper()

            # spread symmetry preference
            sym_spread = None
            if key in {"2W-HCAP","HCAP"}:
                try:
                    hs = []
                    for oc in (m.get("outcomes") or []):
                        h = (oc.get("price") or {}).get("handicap")
                        if h is not None:
                            hs.append(float(str(h)))
                    if len(hs) >= 2 and any(abs(a) == abs(b) and a*b < 0 for a in hs for b in hs if a != b):
                        sym_spread = True
                except Exception:
                    sym_spread = None

            cands.append({
                "key": key,
                "market": m,
                "_period": pdesc,                 # "Live Game" or "Game"
                "_status": status,                # 'O' or 'S'
                "_dg_default": dg_default,
                "_is_main_dynamic": is_main_dynamic,
                "_sym_spread": sym_spread,
            })

    def choose(key_set: set[str]):
        pool = [x for x in cands if x["key"] in key_set]
        if not pool:
            return None, None
        # rank asc (lower is better)
        def r(x):
            period_rank = 0 if x["_period"] == "Live Game" else (1 if x["_period"] == "Game" else 9)
            status_rank = 0 if x["_status"] == "O" else (1 if x["_status"] == "S" else 2)
            main_dyn    = 0 if x["_is_main_dynamic"] else 1
            dg_rank     = 0 if x["_dg_default"] else 1
            sym_rank    = 0 if (x["key"] in {"2W-HCAP","HCAP"} and x["_sym_spread"]) else 1
            return (period_rank, status_rank, main_dyn, dg_rank, sym_rank)
        best = sorted(pool, key=r)[0]
        src = "live" if best["_period"] == "Live Game" else "prematch"
        return best["market"], src

    # pick markets (2-way first; ML can fall back to 3-way)
    ml_mkt,   ml_src = choose({"2W-12"})
    if not ml_mkt:
        ml_mkt, ml_src = choose({"3W-12"})
    sp_mkt, sp_src   = choose({"2W-HCAP","HCAP"})
    tot_mkt, tot_src = choose({"2W-OU","OU"})

    def is_home_outcome(oc):
        price = oc.get("price") or {}
        pid   = str(oc.get("participantId") or oc.get("competitorId") or price.get("participantId") or "")
        if home_id and pid and pid == home_id:
            return True
        desc = (oc.get("description") or "").strip().lower()
        if home_name and home_name.lower() in desc: return True
        if away_name and away_name.lower() in desc: return False
        t = (oc.get("type") or "").strip().upper()
        if t in {"H","HOME","1","TEAM 1"}: return True
        if t in {"A","AWAY","2","TEAM 2"}: return False
        return None

    # MONEYLINE
    if ml_mkt:
        out["ml_status"] = ml_mkt.get("status")
        out["ml_source"] = ml_src
        for oc in (ml_mkt.get("outcomes") or []):
            t = (oc.get("type") or "").strip().upper()
            d = (oc.get("description") or "").strip().lower()
            if t in {"D","DRAW"} or d in {"draw","tie"}:
                continue
            am = _norm_minus((oc.get("price") or {}).get("american"))
            flag = is_home_outcome(oc)
            if flag is True and out["home_ml"] is None:
                out["home_ml"] = am
            elif flag is False and out["away_ml"] is None:
                out["away_ml"] = am

    # SPREAD
    if sp_mkt:
        out["spread_status"] = sp_mkt.get("status")
        out["spread_source"] = sp_src
        for oc in (sp_mkt.get("outcomes") or []):
            price = oc.get("price") or {}
            am = _norm_minus(price.get("american"))
            hcap = price.get("handicap")
            try:
                hcap = float(str(hcap)) if hcap is not None else None
            except Exception:
                hcap = None
            flag = is_home_outcome(oc)
            if flag is True:
                out["home_spread"] = hcap; out["home_spread_price"] = am
            elif flag is False:
                out["away_spread"] = hcap; out["away_spread_price"] = am

    # TOTAL
    if tot_mkt:
        out["total_status"] = tot_mkt.get("status")
        out["total_source"] = tot_src
        for oc in (tot_mkt.get("outcomes") or []):
            price = oc.get("price") or {}
            am = _norm_minus(price.get("american"))
            hcap = price.get("handicap")
            try:
                hcap = float(str(hcap)) if hcap is not None else None
            except Exception:
                hcap = None
            desc = (oc.get("description") or "").strip().lower()
            if desc == "over":
                if out["total_line"] is None and hcap is not None: out["total_line"] = hcap
                out["over_price"] = am
            elif desc == "under":
                if out["total_line"] is None and hcap is not None: out["total_line"] = hcap
                out["under_price"] = am

    return out

# =========================
# Scores layer (per event) with BGS support
# =========================

def fetch_scores(event_id: str) -> Dict[str, Any]:
    """
    Supports:
      1) dict payloads with 'home'/'away' or 'homeTeam'/'awayTeam' + 'clock'/'eventClock'
      2) BGS list payloads with 'latestScore' and 'clock' (period/gameTime), 'gameStatus'
    """
    url = f"{SCORES_BASE}{event_id}"
    resp = http_get(url)
    out = {"home_score": None, "away_score": None, "clock": None, "period": None, "score_status": None}

    if resp is None or resp.status_code == 404 or not (200 <= resp.status_code < 300):
        return out

    try:
        js = resp.json()
    except json.JSONDecodeError:
        return out

    # BGS style: list with dict containing latestScore + clock + gameStatus
    if isinstance(js, list) and js and isinstance(js[0], dict) and ("latestScore" in js[0] or "gameStatus" in js[0]):
        node = js[0]
        latest = node.get("latestScore") or {}
        out["home_score"] = _to_int(latest.get("home"))
        out["away_score"] = _to_int(latest.get("visitor"))

        clk = node.get("clock") or {}
        if isinstance(clk, dict):
            out["clock"] = clk.get("gameTime") or clk.get("displayValue") or clk.get("shortLabel")
            out["period"] = clk.get("period") or clk.get("periodNumber")
        out["score_status"] = node.get("gameStatus") or node.get("status")
        return out

    # Dict style (older/other sports)
    node = js if isinstance(js, dict) else (js[0] if isinstance(js, list) and js else {})
    try:
        out["score_status"] = node.get("status") or node.get("gameStatus")
        home = (node.get("home") or node.get("homeTeam") or {})
        away = (node.get("away") or node.get("awayTeam") or {})
        out["home_score"] = _to_int(home.get("score") or home.get("points"))
        out["away_score"] = _to_int(away.get("score") or away.get("points"))

        clk = node.get("clock") or node.get("eventClock")
        if isinstance(clk, dict):
            out["clock"] = clk.get("displayValue") or clk.get("shortLabel") or clk.get("gameTime")
            out["period"] = clk.get("period") or clk.get("phase")
        elif isinstance(clk, str):
            out["clock"] = clk
    except Exception:
        pass

    return out

# =========================
# Orchestrator (optional, handy for testing)
# =========================

def fetch_bovada_live_games_with_markets(
    sport_types: Optional[List[str]] = None,
    include_prematch: bool = True,
) -> pd.DataFrame:
    """
    Convenience function: returns a DataFrame with events + markets + (live-only) scores.
    Use your ingest to write to DB instead; this is mainly for local debugging/CSV.
    """
    sport_types = sport_types or ["football/college-football"]
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    all_rows: List[Dict[str, Any]] = []

    for spath in sport_types:
        base_df = fetch_events_for_sport(spath, live_only=not include_prematch)
        if base_df.empty:
            continue

        for _, r in base_df.iterrows():
            link = r.get("link")
            ev_node = fetch_event_node_by_link(link) if isinstance(link, str) else None
            time.sleep(SLEEP_BETWEEN)

            mk = extract_key_markets(
                ev_node=ev_node,
                home_id=str(r.get("home_competitor_id") or ""),
                away_id=str(r.get("away_competitor_id") or ""),
                home_name=r.get("home_team"),
                away_name=r.get("away_team"),
            ) if ev_node else {}

            # scores only for live
            sc = {"home_score": None, "away_score": None, "clock": None, "period": None, "score_status": None}
            if bool(r.get("is_live")):
                sc = fetch_scores(str(r["event_id"]))
                time.sleep(SLEEP_BETWEEN)

            row = {
                "scraped_at_utc": scraped_at,
                "sport": r.get("sport"),
                "event_id": r.get("event_id"),
                "description": r.get("description"),
                "link": r.get("link"),
                "start_time_utc": r.get("start_time_utc"),
                "status": r.get("status"),
                "last_modified_utc": r.get("last_modified_utc"),
                "home_team": r.get("home_team"),
                "away_team": r.get("away_team"),
                "is_live": bool(r.get("is_live")),
                # Markets
                "home_ml": mk.get("home_ml"),
                "away_ml": mk.get("away_ml"),
                "ml_status": mk.get("ml_status"),
                "ml_source": mk.get("ml_source"),
                "home_spread": mk.get("home_spread"),
                "home_spread_price": mk.get("home_spread_price"),
                "away_spread": mk.get("away_spread"),
                "away_spread_price": mk.get("away_spread_price"),
                "spread_status": mk.get("spread_status"),
                "spread_source": mk.get("spread_source"),
                "total_line": mk.get("total_line"),
                "over_price": mk.get("over_price"),
                "under_price": mk.get("under_price"),
                "total_status": mk.get("total_status"),
                "total_source": mk.get("total_source"),
                # Scores
                "home_score": sc.get("home_score"),
                "away_score": sc.get("away_score"),
                "clock": sc.get("clock"),
                "period": sc.get("period"),
                "score_status": sc.get("score_status"),
            }
            all_rows.append(row)

    df = pd.DataFrame(all_rows).reset_index(drop=True)

    # types
    for c in ["home_score", "away_score"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in ["home_spread", "away_spread", "total_line"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["home_ml", "away_ml", "home_spread_price", "away_spread_price", "over_price", "under_price"]:
        if c in df.columns: df[c] = df[c].astype("string").str.replace("−", "-", regex=False)

    return df

# CLI (optional)
if __name__ == "__main__":
    df = fetch_bovada_live_games_with_markets()
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)
    print(df.head(50))
    if not df.empty:
        df.to_csv("bovada_live_markets_v2.csv", index=False)
        print("\nSaved bovada_live_markets_v2.csv")
    else:
        print("\nNo rows returned.")
