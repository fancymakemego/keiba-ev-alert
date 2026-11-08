"""発走10分前に、次のどちらかに当てはまる馬を ntfy に通知する。

  A（単勝向き）: 亀AI推奨 & 亀AIの的中率上位6頭 & 単勝10〜50倍
  B（複勝向き）: 亀AI推奨 & FRONT RUNNER の 予測勝率×単勝オッズ > 100%
                 & 1番人気の予測勝率 20%以下（荒れやすいレース）

2026-05〜11 の検証（単勝・複勝100円、確定オッズ）: A は単勝127%、B は複勝121%。
ただし誤差が大きく、9〜10月は B が複勝100%前後。report.py で実戦の成績を追う。

GitHub Actions で1日2回起動し、担当レースが終わるまで待機する。
  --part am : 発走 13:30 より前 / --part pm : 13:30 以降
環境変数: NTFY_TOPIC, KAME_ID, KAME_PW, LOG_KEY（Secrets）, LEAD_MIN（既定10）, DRY_RUN=1
"""
import argparse
import datetime as dt
import json
import os
import time
import urllib.request

import fr_api
import kame_api
import secure_log

JST = dt.timezone(dt.timedelta(hours=9))
SPLIT = dt.time(13, 30)
LEAD = int(os.environ.get("LEAD_MIN", "10"))
DRY = os.environ.get("DRY_RUN") == "1"

# 条件の数値（変えるときはここだけ）
A_MIN_ODDS, A_MAX_ODDS, A_HITRANK = 10, 50, 6
B_EV_MIN, B_FAV_P_MAX = 1.0, 0.20


def now():
    return dt.datetime.now(JST)


def notify(title, message, click=None, tags="horse_racing", priority=4):
    topic = os.environ.get("NTFY_TOPIC", "")
    if DRY or not topic:
        print(f"[notify{' (dry)' if DRY else ' (NTFY_TOPIC 未設定)'}] {title}\n{message}\n")
        return
    msg = {"topic": topic, "title": title, "message": message, "tags": [tags], "priority": priority}
    if click:
        msg["click"] = click
    req = urllib.request.Request("https://ntfy.sh/", data=json.dumps(msg).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20).read()


def judge(rows, kame):
    """rows: fr_api.evaluate の結果。kame: {"picks": [...], "hitrank": [...]}。
    推奨馬ごとに条件 A/B の判定を返す。"""
    if not rows:
        return []
    fav = min(rows, key=lambda r: r["popularity"] or 99)
    fav_p = fav["p"]
    out = []
    for r in rows:
        if r["number"] not in kame["picks"]:
            continue
        hr = kame["hitrank"].index(r["number"]) + 1 if r["number"] in kame["hitrank"] else None
        a = hr is not None and hr <= A_HITRANK and A_MIN_ODDS <= r["odds"] < A_MAX_ODDS
        b = r["ev"] > B_EV_MIN and fav_p <= B_FAV_P_MAX
        out.append({**r, "hitrank": hr, "fav_p": round(fav_p, 4), "A": a, "B": b})
    return out


def check_race(race, date, kame):
    rows = fr_api.evaluate(fr_api.entries(race["id"]))
    if not rows or all(r["odds"] is None for r in rows):
        return False
    label = f"{race['venue']}{race['raceNumber']}R"
    js = judge(rows, kame)
    hits = [j for j in js if j["A"] or j["B"]]
    secure_log.append(date, {"raceId": race["id"], "label": label, "start": race["startTime"],
                             "checkedAt": now().strftime("%H:%M"), "kame": js})
    print(f"{now():%H:%M} {label}: 推奨{len(js)}頭 通知{len(hits)}頭")
    if hits:
        lines = []
        for j in sorted(hits, key=lambda j: j["odds"]):
            tag = "/".join(t for t, ok in (("A単勝", j["A"]), ("B複勝", j["B"])) if ok)
            lines.append(f"[{tag}] {j['number']} {j['name']} {j['odds']:.1f}倍"
                         + (f"（{j['popularity']}人気）" if j.get("popularity") else ""))
        notify(f"{label} {race['startTime']}発走 {race['name']}", "\n".join(lines), fr_api.race_url(race["id"]))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["am", "pm", "all"], default="all")
    ap.add_argument("--date", help="YYYY-MM-DD（既定: 今日 JST）")
    ap.add_argument("--check", action="store_true", help="ログイン・記事の読み取り・暗号化だけ試して終わる（通知しない）")
    a = ap.parse_args()
    date = a.date or now().strftime("%Y-%m-%d")
    if a.check:
        kame = kame_api.picks_for(date)
        print(f"OK 亀AI {date}: {len(kame)} レース / 推奨 {sum(len(v['picks']) for v in kame.values())} 頭")
        secure_log._f().decrypt(secure_log._f().encrypt(b"test"))
        print("OK LOG_KEY")
        print("OK NTFY_TOPIC" if os.environ.get("NTFY_TOPIC") else "NG NTFY_TOPIC 未設定")
        return

    todo = []
    for r in fr_api.races(date):
        st = dt.datetime.strptime(f"{date} {r['startTime']}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        if (a.part == "am" and st.time() >= SPLIT) or (a.part == "pm" and st.time() < SPLIT) or st <= now():
            continue
        todo.append((st, r))
    print(f"{date} part={a.part}: 対象 {len(todo)} レース / {LEAD}分前")
    if not todo:
        return

    try:
        kame = kame_api.picks_for(date)
    except Exception as e:
        notify("競馬アラート: 亀AIの推奨馬を取得できません", f"{date} {a.part}: {e}\nこの部の通知は止まります。",
               tags="warning", priority=4)
        raise
    print(f"亀AI: {len(kame)} レース / 推奨 {sum(len(v['picks']) for v in kame.values())} 頭")

    queue = [(st - dt.timedelta(minutes=LEAD), st, r) for st, r in todo
             if (r["venue"], r["raceNumber"]) in kame]
    while queue:
        queue.sort(key=lambda x: x[0])
        due, st, race = queue[0]
        wait = (due - now()).total_seconds()
        if wait > 0:
            time.sleep(min(wait, 60))
            continue
        queue.pop(0)
        try:
            done = check_race(race, date, kame[(race["venue"], race["raceNumber"])])
        except Exception as e:
            print(f"{race['id']} 取得失敗: {e}")
            done = False
        if not done:
            if now() + dt.timedelta(minutes=1) < st - dt.timedelta(minutes=2):
                queue.append((now() + dt.timedelta(minutes=1), st, race))
            else:
                print(f"{race['id']} オッズ取得できず、スキップ")


if __name__ == "__main__":
    main()
