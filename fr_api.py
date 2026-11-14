"""FRONT RUNNER (frontrunner-race.com) の公開 API を読む小さなクライアント。

アクセスは控えめに: 1レースにつき発走10分前の1回（オッズ未取得なら数回）だけ取りに行く。
"""
import json
import time
import urllib.error
import urllib.request

BASE = "https://frontrunner-race.com"
UA = "keiba-ev-alert/1.0 (personal notifier)"


def get(path, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404 or i == retries - 1:
                raise
            time.sleep(5 * (i + 1))
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(5 * (i + 1))


def races(date):
    """date の全レース（会場名つき）。開催の無い日は API が 404 を返すので空にする。"""
    out = []
    try:
        day = get(f"/api/races?date={date}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise
    for v in day.get("venues", []):
        for r in v.get("races", []):
            out.append({**r, "venue": v["name"]})
    return out


def entries(race_id):
    return get(f"/api/race/{race_id}/entries").get("entries", [])


def results(date):
    return {r["raceId"]: r for r in get(f"/api/results?date={date}").get("results", [])}


def race_url(race_id):
    return f"{BASE}/race.html?id={race_id}"


def evaluate(es):
    """各馬の 予測勝率(0-1)・オッズ・期待値(勝率×オッズ) を返す。取消・除外とオッズ無しは除く。

    predictWinRate はレースによって 0-1 か % かが混在するので、サイトと同じく
    「全馬の最大値が1以下なら確率」とみなす。
    """
    wr = [e["predictWinRate"] for e in es if e.get("predictWinRate") is not None]
    if not wr:
        return []
    scale = 1 if max(wr) <= 1 else 0.01
    out = []
    for e in es:
        if e.get("predictWinRate") is None or e.get("odds") is None or e.get("runStateLabel"):
            continue
        p = e["predictWinRate"] * scale
        out.append({
            "number": e["number"], "name": e["name"], "p": round(p, 4),
            "odds": e["odds"], "popularity": e.get("popularity"),
            "ev": round(p * e["odds"], 3),
        })
    return out
