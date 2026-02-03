import os
import json
import hashlib
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime, timezone

import urllib.request
from bs4 import BeautifulSoup

TARGET_URL = "https://www.di-ksp.jp/school"
KEYWORD = "硬式テニス"
STATE_FILE = "state.json"
TIMEOUT_SEC = 25

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

FROM_EMAIL = os.environ.get("WATCH_FROM_EMAIL", "")
TO_EMAIL = os.environ.get("WATCH_TO_EMAIL", "")
APP_PASSWORD = os.environ.get("WATCH_APP_PASSWORD", "")


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
        return res.read().decode("utf-8", errors="ignore")


def extract_hard_tennis_text(html: str) -> str:
    """
    /school ページ内から「硬式テニス」に関係する情報だけを抽出して
    文字列として返す（この文字列のハッシュで更新判定）
    """
    soup = BeautifulSoup(html, "html.parser")

    # ページ内で「硬式テニス」を含むテキストを持つ要素を拾う
    hits = []
    for el in soup.find_all(string=True):
        txt = (el or "").strip()
        if txt and KEYWORD in txt:
            parent = el.parent
            # 近くにリンクがあれば一緒に取る（教室詳細へのURLなど）
            link = parent.find("a") if parent else None
            href = ""
            if link and link.get("href"):
                href = link.get("href")
                if href.startswith("/"):
                    href = "https://www.di-ksp.jp" + href
            hits.append(f"{txt} {href}".strip())

    # 重複削除＆安定ソート（順序変化による誤検知を減らす）
    unique = sorted(set(hits))
    return "\n".join(unique)


def sha256(s: str) -
