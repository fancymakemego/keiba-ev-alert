"""亀谷競馬サロンの記事から語句（馬名・種牡馬名など）を探し、見つかった前後の文章を ntfy に送る。
有料記事なので Actions のログには件数しか出さない。

  python salon_search.py --search 2歳戦診断 --since 2026-06-01 --names "馬A,馬B"
  python salon_search.py --search フライトライン --body --since 2026-01-01 --names フライトライン
環境変数: KAME_ID, KAME_PW, NTFY_TOPIC
"""
import argparse
import html
import json
import re
import time
import urllib.parse

import kame_api
from alert import notify

CHUNK = 1200      # ntfy 1通あたりの文字数（4096バイト上限に収める）
MAX_MSGS = 40     # 送りすぎ防止


def merged_snippets(text, names, before=250, after=450):
    spans = sorted((max(0, m.start() - before), m.end() + after)
                   for n in names for m in re.finditer(re.escape(n), text))
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [text[s:e].replace("\n", " ") for s, e in merged]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", required=True, help="WordPress の検索語")
    ap.add_argument("--count", type=int, default=4, help="新しい順に何本読むか（--since が無いとき）")
    ap.add_argument("--since", default="", help="YYYY-MM-DD 以降の記事をすべて読む")
    ap.add_argument("--body", action="store_true", help="タイトルに検索語が無い記事も読む（本文検索）")
    ap.add_argument("--names", required=True, help="本文で探す語（カンマ区切り）")
    ap.add_argument("--label", default="", help="通知の見出し")
    a = ap.parse_args()
    names = [n.strip() for n in a.names.split(",") if n.strip()]

    op = kame_api.login()
    posts, page = [], 1
    while page <= 10:
        q = urllib.parse.urlencode({"search": a.search, "per_page": 50, "page": page, "_fields": "link,title,date"})
        try:
            items = json.loads(kame_api._get(op, f"{kame_api.BASE}/wp-json/wp/v2/posts?{q}"))
        except Exception:
            break
        if not items:
            break
        posts += [p for p in items
                  if (a.body or a.search in html.unescape(p["title"]["rendered"]))
                  and (not a.since or p["date"][:10] >= a.since)]
        if not a.since or items[-1]["date"][:10] < a.since:
            break
        page += 1
    if not a.since:
        posts = posts[: a.count]

    head = a.label or f"サロン検索「{a.search}」"
    msgs = []
    for p in posts:
        title = html.unescape(p["title"]["rendered"])
        t = kame_api.text_of(kame_api._get(op, p["link"]))
        if "続きを読むにはログインしてください" in t:
            raise SystemExit("ログインできなかった")
        t = t[t.find(title):t.find("新着記事/コンテンツ")] if title in t else t
        snips = merged_snippets(t, names)
        if snips:
            body = f"{p['date'][:10]} {title}\n…" + " …\n…".join(snips) + "…"
            parts = [body[i:i + CHUNK] for i in range(0, len(body), CHUNK)]
            for i, part in enumerate(parts, 1):
                msgs.append((f"{head}｜{title[:24]}" + (f" ({i}/{len(parts)})" if len(parts) > 1 else ""), part))
        time.sleep(1)
    print(f"記事 {len(posts)} 本 / 該当記事 {len({m[0].split(' (')[0] for m in msgs})} 本 / 通知 {len(msgs)} 通")
    if not msgs:
        notify(head, f"記事{len(posts)}本の中に見つかりませんでした。", tags="mag", priority=3)
        return
    if len(msgs) > MAX_MSGS:
        notify(head, f"該当が多いため、新しい順に{MAX_MSGS}通だけ送ります（全{len(msgs)}通）。", tags="mag", priority=3)
    for t, m in msgs[:MAX_MSGS]:
        notify(t, m, tags="mag", priority=2)
        time.sleep(1)
    notify(f"{head}｜完了", f"記事{len(posts)}本を検索、{min(len(msgs), MAX_MSGS)}通送信しました。", tags="white_check_mark", priority=2)


if __name__ == "__main__":
    main()
