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


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_mail(subject: str, body: str) -> None:
    if not (FROM_EMAIL and TO_EMAIL and APP_PASSWORD):
        raise RuntimeError("メール設定が未入力です（Secrets: WATCH_FROM_EMAIL / WATCH_TO_EMAIL / WATCH_APP_PASSWORD）")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(FROM_EMAIL, APP_PASSWORD)
        server.send_message(msg)


def main():
    html = fetch_html(TARGET_URL)
    tennis_text = extract_hard_tennis_text(html)

    # もしページ構造変化等で抽出が空になった場合は、誤通知を避けるため通知しない
    if not tennis_text.strip():
        print("No hard tennis text found; skip notify to avoid false positives.")
        return

    new_hash = sha256(tennis_text)
    state = load_state()

    old_hash = state.get("hard_tennis_hash")
    old_text = state.get("hard_tennis_text", "")

    # 初回は記録のみ（通知なし）
    if not old_hash:
        state["hard_tennis_hash"] = new_hash
        state["hard_tennis_text"] = tennis_text
        save_state(state)
        print("Initialized state (no email).")
        return

    if new_hash != old_hash:
        now_jst = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        subject = "【硬式テニス】DI-KSP 教室情報に更新がありました"
        body = (
            f"更新を検知しました（{now_jst}）\n\n"
            f"対象ページ: {TARGET_URL}\n\n"
            "▼ 現在の『硬式テニス』関連抽出（最新版）\n"
            "----------------------------------------\n"
            f"{tennis_text}\n\n"
            "▼ 前回の抽出（参考）\n"
            "----------------------------------------\n"
            f"{old_text}\n"
        )
        send_mail(subject, body)

        # state更新（次回比較用）
        state["hard_tennis_hash"] = new_hash
        state["hard_tennis_text"] = tennis_text
        save_state(state)
        print("Updated & notified.")
    else:
        print("No change.")


if __name__ == "__main__":
    main()
