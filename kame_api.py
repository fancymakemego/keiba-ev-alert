"""亀谷競馬サロン「うまく当たる亀AI推奨馬」の当日記事を、会員ログインで読んで解析する。

記事は前日に公開される。1日に1〜2回（午前の部・午後の部の起動時）だけ読む。
ID・パスワードは環境変数 KAME_ID / KAME_PW（GitHub Secrets）から読み、表示・保存しない。
"""
import html
import http.cookiejar
import json
import os
import re
import urllib.parse
import urllib.request

BASE = "https://www.keiba-salon.com"
UA = "Mozilla/5.0 (keiba-ev-alert personal)"
TITLE = "うまく当たる「亀AI」推奨馬/"


class KameError(Exception):
    pass


def _opener():
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", UA)]
    return op


def _get(op, url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    with op.open(url, body, timeout=30) as r:
        return r.read().decode("utf-8", errors="ignore")


def text_of(page):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t)).replace("​", "")
    return re.sub(r"\n\s*\n+", "\n", t)


def parse(text):
    """記事本文 → {(会場, R番号): {"picks": [馬番...], "hitrank": [馬番...]}}"""
    out, cur, mode = {}, None, None
    for ln in text.splitlines():
        ln = ln.strip()
        m = re.fullmatch(r"(\S+?)(\d{1,2})R", ln)
        if m:
            cur = (m[1], int(m[2]))
            out[cur] = {"picks": [], "hitrank": []}
            mode = "picks"
            continue
        if ln.startswith("的中率"):
            mode = "rank"
            continue
        if cur is None:
            continue
        if mode == "picks":
            m = re.match(r"(\d{1,2})\D", ln)
            if m:
                out[cur]["picks"].append(int(m[1]))
        elif mode == "rank" and re.fullmatch(r"[\d,\s]+", ln):
            out[cur]["hitrank"] = [int(x) for x in re.split(r"[,\s]+", ln) if x]
            mode = None
    return out


def find_article(op, date):
    """date (YYYY-MM-DD) のレースの記事 URL。"""
    y, mo, d = (int(x) for x in date.split("-"))
    want = f"{TITLE}{mo}月{d}日"
    q = urllib.parse.urlencode({"search": "亀AI", "per_page": 20, "_fields": "link,title"})
    for p in json.loads(_get(op, f"{BASE}/wp-json/wp/v2/posts?{q}")):
        if html.unescape(p["title"]["rendered"]).startswith(want):
            return p["link"]
    raise KameError(f"{mo}/{d} の亀AI記事がまだ見つからない")


def login():
    uid, pw = os.environ.get("KAME_ID"), os.environ.get("KAME_PW")
    if not uid or not pw:
        raise KameError("KAME_ID / KAME_PW が未設定")
    op = _opener()
    page = _get(op, BASE + "/login/")
    token = re.search(r'name="token" value="([^"]+)"', page)
    if not token:
        raise KameError("ログイン画面の形式が変わった")
    _get(op, BASE + "/at", {"login": uid, "password": pw, "rurl": BASE, "token": token[1]})
    return op


def picks_for(date):
    op = login()
    url = find_article(op, date)
    text = text_of(_get(op, url))
    if "続きを読むにはログインしてください" in text:
        raise KameError("ログインできなかった（ID・パスワードを確認）")
    data = parse(text[text.find("推奨馬】"):text.find("新着記事/コンテンツ")])
    if not data:
        raise KameError("記事から推奨馬を読み取れなかった")
    return data
