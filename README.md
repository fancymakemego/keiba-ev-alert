# keiba-ev-alert

発走10分前に、次の条件に当てはまる馬を ntfy でスマホへ通知する。

| 条件 | 内容 | 検証（2026-05〜11） |
|---|---|---|
| A（単勝向き） | 亀AI推奨 & 亀AIの的中率上位6頭 & 単勝10〜50倍 | 単勝回収 127%（443頭） |
| B（複勝向き） | 亀AI推奨 & FRONT RUNNER の 予測勝率×単勝オッズ > 100% & 1番人気の予測勝率 20%以下 | 複勝回収 121%（639頭） |

検証の誤差は大きい（B は ±30% 程度、9〜10月は100%前後）。実戦の成績は月曜朝の週間レポートで追う。

- 亀AI推奨: 亀谷競馬サロン「うまく当たる亀AI推奨馬」（会員記事、`kame_api.py` が当日朝にログインして読む）
- 予測勝率・オッズ・結果: FRONT RUNNER（frontrunner-race.com）の API（`fr_api.py`）
- 記録は有料情報を含むので `log/*.enc` に暗号化して保存（`secure_log.py`）

## 動かし方

| 起動 | 時刻（JST） | 内容 |
|---|---|---|
| cron-job.org → workflow_dispatch `part=am` | 毎日 9:30 | 13:30 より前に発走するレース |
| cron-job.org → workflow_dispatch `part=pm` | 毎日 12:30 | 13:30 以降に発走するレース |

開催の無い日はすぐ終わる。条件の数値は `alert.py` 冒頭の定数。

Secrets: `NTFY_TOPIC` / `KAME_ID` / `KAME_PW` / `LOG_KEY`（記録の暗号鍵。任意の長い文字列）
