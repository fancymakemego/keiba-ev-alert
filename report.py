"""通知した馬（条件 A / B）の成績を、実際の単勝・複勝の払戻で集計する。

  python report.py            # 直近7日
  python report.py --days 28
  python report.py --notify   # ntfy にも送る
"""
import argparse
import datetime as dt

import fr_api
import secure_log
from alert import JST, notify


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--notify", action="store_true")
    a = ap.parse_args()
    since = (dt.datetime.now(JST).date() - dt.timedelta(days=a.days)).isoformat()

    groups = {"A（単勝向き）": [], "B（複勝向き）": [], "亀AI推奨すべて": []}
    for date in secure_log.dates():
        if date <= since:
            continue
        res = fr_api.results(date)
        for rec in secure_log.load(date):
            r = res.get(rec["raceId"])
            if not r or r.get("status") != "confirmed":
                continue
            win = {p["numbers"]: p["amount"] for p in r.get("payouts", []) if p["type"] == "単勝"}
            plc = {p["numbers"]: p["amount"] for p in r.get("payouts", []) if p["type"] == "複勝"}
            scratched = {p["number"] for p in r["placings"] if p.get("runStateLabel")}
            for j in rec["kame"]:
                if j["number"] in scratched:
                    continue  # 取消・除外は返還
                row = {"win": win.get(str(j["number"]), 0), "plc": plc.get(str(j["number"]), 0)}
                groups["亀AI推奨すべて"].append(row)
                if j["A"]:
                    groups["A（単勝向き）"].append(row)
                if j["B"]:
                    groups["B（複勝向き）"].append(row)

    lines = [f"直近{a.days}日（各100円・実際の払戻）"]
    for name, rows in groups.items():
        n = len(rows)
        if not n:
            lines.append(f"{name}: データなし")
            continue
        w, p = sum(r["win"] for r in rows), sum(r["plc"] for r in rows)
        lines.append(f"{name}: {n}頭 単勝{sum(r['win'] > 0 for r in rows)}勝 回収{w / n:.0f}% / "
                     f"複勝{sum(r['plc'] > 0 for r in rows)}回 回収{p / n:.0f}%")
    text = "\n".join(lines)
    print(text)
    if a.notify:
        notify("競馬アラート 週間成績", text, tags="bar_chart", priority=3)


if __name__ == "__main__":
    main()
