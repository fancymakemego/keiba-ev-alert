"""発走 N 分前に「予測勝率 × 単勝オッズ」が基準を超える馬を ntfy に通知する。

GitHub Actions で1日2回（午前の部・午後の部）起動し、担当レースが終わるまで待機する。
  --part am : 発走 13:30 より前のレース
  --part pm : 発走 13:30 以降のレース
開催が無い日はすぐ終了する。

環境変数
  NTFY_TOPIC  通知先トピック（必須。Secrets に入れる）
  EV_MIN      期待値の下限（既定 1.0 = 100%）
  MIN_ODDS    通知する単勝オッズの下限（既定 10）
  MAX_ODDS    上限（既定 0 = 上限なし）
  LEAD_MIN    発走何分前に見るか（既定 10）
  DRY_RUN     1 なら通知せず表示だけ
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import time
import urllib.request

import fr_api

JST = dt.timezone(dt.timedelta(hours=9))
SPLIT = dt.time(13, 30)
EV_MIN = float(os.environ.get("EV_MIN", "1.0"))
MIN_ODDS = float(os.environ.get("MIN_ODDS", "10"))
MAX_ODDS = float(os.environ.get("MAX_ODDS", "0"))
LEAD = int(os.environ.get("LEAD_MIN", "10"))
DRY = os.environ.get("DRY_RUN") == "1"
LOG_DIR = pathlib.Path(__file__).parent / "log"


def now():
    return dt.datetime.now(JST)


def notify(title, message, click, tags="horse_racing", priority=4):
    topic = os.environ.get("NTFY_TOPIC", "")
    if DRY or not topic:
        print(f"[notify{' (dry)' if DRY else ' (NTFY_TOPIC 未設定)'}] {title}\n{message}\n")
        return
    body = json.dumps({"topic": topic, "title": title, "message": message,
                       "click": click, "tags": [tags], "priority": priority}).encode()
    req = urllib.request.Request("https://ntfy.sh/", data=body,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20).read()


def pick(rows):
    return [r for r in rows if r["ev"] > EV_MIN and r["odds"] >= MIN_ODDS
            and (MAX_ODDS <= 0 or r["odds"] <= MAX_ODDS)]


def check_race(race, date):
    """オッズが出ていれば判定して True。まだなら False（あとで再試行）。"""
    rows = fr_api.evaluate(fr_api.entries(race["id"]))
    if not rows:
        return False
    hits = sorted(pick(rows), key=lambda r: -r["ev"])
    label = f"{race['venue']}{race['raceNumber']}R"
    # 記録はオッズ条件に関係なく EV 基準超えを全部残す（あとで回収率を検証するため）
    log_path = LOG_DIR / f"{date}.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "raceId": race["id"], "label": label, "start": race["startTime"],
            "checkedAt": now().strftime("%H:%M"),
            "ev_over": [r for r in rows if r["ev"] > EV_MIN],
            "notified": [r["number"] for r in hits],
        }, ensure_ascii=False) + "\n")
    print(f"{now():%H:%M} {label} {race['name']}: {len(hits)}頭")
    if hits:
        lines = [f"{r['number']} {r['name']}  {r['p']*100:.1f}% × {r['odds']:.1f}倍 = {r['ev']*100:.0f}%"
                 + (f"（{r['popularity']}人気）" if r.get("popularity") else "")
                 for r in hits]
        notify(f"{label} {race['startTime']}発走 {race['name']}",
               "\n".join(lines), fr_api.race_url(race["id"]))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["am", "pm", "all"], default="all")
    ap.add_argument("--date", help="YYYY-MM-DD（既定: 今日 JST）")
    a = ap.parse_args()
    date = a.date or now().strftime("%Y-%m-%d")

    todo = []
    for r in fr_api.races(date):
        st = dt.datetime.strptime(f"{date} {r['startTime']}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        if a.part == "am" and st.time() >= SPLIT:
            continue
        if a.part == "pm" and st.time() < SPLIT:
            continue
        if st <= now():
            continue  # 発走済み
        todo.append((st, r))
    print(f"{date} part={a.part}: 対象 {len(todo)} レース / EV>{EV_MIN} オッズ{MIN_ODDS}〜{MAX_ODDS or '∞'} / {LEAD}分前")
    if not todo:
        return
    LOG_DIR.mkdir(exist_ok=True)

    # (見に行く時刻, 発走時刻, レース)。オッズ未発表なら1分後に入れ直し、発走2分前で諦める
    queue = [(st - dt.timedelta(minutes=LEAD), st, r) for st, r in todo]
    while queue:
        queue.sort(key=lambda x: x[0])
        due, st, race = queue[0]
        wait = (due - now()).total_seconds()
        if wait > 0:
            time.sleep(min(wait, 60))
            continue
        queue.pop(0)
        try:
            done = check_race(race, date)
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
