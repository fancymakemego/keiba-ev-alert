# keiba-ev-alert

FRONT RUNNER（frontrunner-race.com）の **予測勝率 × 単勝オッズ** が基準を超えた馬を、
発走10分前に ntfy でスマホへ通知する。

- 条件（`.github/workflows/alert.yml` の env で変更）: `EV_MIN=1.0`（100%超）、`MIN_ODDS=10`（10倍以上）、`MAX_ODDS=0`（上限なし）、`LEAD_MIN=10`
- 通知は1レース1件。タップで FRONT RUNNER の出馬表が開く
- 記録: オッズ条件に関係なく EV 100%超の馬を `log/YYYY-MM-DD.jsonl` に残す（Actions が commit）
- 週間成績: 月曜朝に `report.py` が直近7日の回収率（確定オッズ）を ntfy に送る

## 動かし方

| 起動 | 時刻（JST） | 内容 |
|---|---|---|
| cron-job.org → workflow_dispatch `part=am` | 毎日 9:30 | 13:30 より前に発走するレース |
| cron-job.org → workflow_dispatch `part=pm` | 毎日 12:30 | 13:30 以降に発走するレース |

開催の無い日はすぐ終わる。GitHub の `schedule:` は遅れるので予備。

Secrets: `NTFY_TOPIC`（ntfy のトピック名）

手元で試す: `DRY_RUN=1 python alert.py --part am`（通知せず表示だけ）
