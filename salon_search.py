"""亀谷競馬サロンの記事から馬名を探し、見つかった前後の文章を ntfy に送る（有料記事なので Actions のログには出さない）。

  python salon_search.py --search 2歳戦診断 --count 4 --names "馬A,馬B"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", required=True, help="記事タイトルの検索語")
    ap.add_argument("--count", type=int, default=4, help="新しい順に何本読むか")
    ap.add_argument("--names", required=True, help="馬名（カンマ区切り）")
    ap.add_argument("--label", default="", help="通知の見出し")
    ap.add_argument("--since", default="", help="YYYY-MM-DD 以降の記事をすべて読む（指定時は --count を無視）")
    a = ap.parse_args()
    names = [n.strip() for n in a.names.split(",") if n.strip()]

    op = kame_api.login()
    posts, page = [], 1
    while True:
        q = urllib.parse.urlencode({"search": a.search, "per_page": 50, "page": page, "_fields": "link,title,date"})
        try:
            items = json.loads(kame_api._get(op, f"{kame_api.BASE}/wp-json/wp/v2/posts?{q}"))
        except Exception:
            break
        if not items:
            break
        posts += [p for p in items if a.search in html.unescape(p["title"]["rendered"])
                  and (not a.since or p["date"][:10] >= a.since)]
        if not a.since or items[-1]["date"][:10] < a.since or page >= 10:
            break
        page += 1
    if not a.since:
        posts = posts[: a.count]
    found = []
    for p in posts:
        title = html.unescape(p["title"]["rendered"])
        t = kame_api.text_of(kame_api._get(op, p["link"]))
        t = t[t.find(title):t.find("新着記事/コンテンツ")] if title in t else t
        if "続きを読むにはログインしてください" in t:
            raise SystemExit("ログインできなかった")
        for n in names:
            for m in re.finditer(re.escape(n), t):
                s = t[max(0, m.start() - 250):m.end() + 350].replace("\n", " ")
                found.append(f"■{n}（{title[:30]}）\n…{s}…")
        time.sleep(1)
    print(f"記事 {len(posts)} 本 / 該当 {len(found)} 件")
    head = a.label or f"サロン検索「{a.search}」"
    if not found:
        notify(head, f"記事{len(posts)}本の中に、指定した馬の名前は見つかりませんでした。", tags="mag", priority=3)
        return
    for i, f in enumerate(found, 1):
        notify(f"{head} {i}/{len(found)}", f[:3800], tags="mag", priority=3)
        time.sleep(1)


if __name__ == "__main__":
    main()
