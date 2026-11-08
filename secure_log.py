"""記録（亀AI推奨＝有料情報を含む）を暗号化して log/YYYY-MM-DD.enc に保存する。

鍵は環境変数 LOG_KEY（GitHub Secrets。好きな長い文字列）から作る。公開リポジトリでも中身は読めない。
"""
import base64
import hashlib
import json
import os
import pathlib

from cryptography.fernet import Fernet

LOG_DIR = pathlib.Path(__file__).parent / "log"


def _f():
    key = os.environ.get("LOG_KEY")
    if not key:
        raise RuntimeError("LOG_KEY が未設定")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def load(date):
    p = LOG_DIR / f"{date}.enc"
    if not p.exists():
        return []
    return json.loads(_f().decrypt(p.read_bytes()))


def append(date, rec):
    recs = load(date)
    recs.append(rec)
    LOG_DIR.mkdir(exist_ok=True)
    (LOG_DIR / f"{date}.enc").write_bytes(_f().encrypt(json.dumps(recs, ensure_ascii=False).encode()))


def dates():
    return sorted(p.stem for p in LOG_DIR.glob("*.enc"))
