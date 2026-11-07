"""通知・記録した馬の成績を集計する（回収率は確定オッズで計算）。

  python report.py            # 直近7日
  python report.py --days 28
  python report.py --notify   # 結果を ntfy にも送る
"""
import argparse
import datetime as dt
import json
import os
import pathlib

import fr_api
from alert import JST, notify

LOG_DIR = pathlib.Path(__file__).parent / "log"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--notify", action="store_true")
    a = ap.parse_args()
    since = dt.datetime.now(JST).date() - dt.timedelta(days=a.days)
    min_odds = float(os.environ.get("MIN_ODDS", "10"))

    groups = {"通知した馬": [], "EV100%超すべて": []}
    drift = []
    for path in sorted(LOG_DIR.glob("*.jsonl")):
        date = path.stem
        if dt.date.fromisoformat(date) <= since:
            continue
        res = fr_api.results(date)
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            r = res.get(rec["raceId"])
            if not r or r.get("status") != "confirmed":
                continue
            final = {p["number"]: p for p in r["placings"]}
            for h in rec["ev_over"]:
                f = final.get(h["number"])
                if not f or f.get("runStateLabel"):
                    continue  # 取消・除外は返還なので数えない
                row = {"won": f.get("rank") == 1, "final_odds": f.get("odds") or h["odds"], "odds": h["odds"]}
                groups["EV100%超すべて"].append(row)
                if h["number"] in rec["notified"]:
                    groups["通知した馬"].append(row)
                    drift.append(row["final_odds"] / h["odds"])

    lines = [f"直近{a.days}日（単勝100円ずつ・確定オッズで計算）"]
    for name, rows in groups.items():
        n = len(rows)
        if not n:
            lines.append(f"{name}: データなし")
            continue
        wins = sum(r["won"] for r in rows)
        ret = sum(r["final_odds"] * 100 for r in rows if r["won"])
        lines.append(f"{name}: {n}頭 {wins}勝 回収率 {ret / n:.1f}%（収支 {ret - n * 100:+,.0f}円）")
    if drift:
        drift.sort()
        lines.append(f"通知時→確定のオッズ変化（中央値）: ×{drift[len(drift) // 2]:.2f}")
    text = "\n".join(lines)
    print(text)
    if a.notify:
        notify("競馬EVアラート 週間成績", text, "https://github.com/fancymakemego/keiba-ev-alert", tags="bar_chart", priority=3)


if __name__ == "__main__":
    main()
