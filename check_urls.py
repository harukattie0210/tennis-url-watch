import hashlib
import json
import os
import smtplib
import ssl
from email.mime.text import MIMEText

import urllib.request

# ===== 設定（ここだけ変更すればOK）=====
WATCH_URLS = [
    "https://www.di-ksp.jp/school",
]

KEYWORDS = ["硬式テニス"]  # この単語が含まれる部分だけを対象にする（不要なら空にしてOK）

MAIL_SUBJECT = "【硬式テニス】教室情報が更新されました"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

FROM_EMAIL = os.environ.get("WATCH_FROM_EMAIL", "")
TO_EMAIL = os.environ.get("WATCH_TO_EMAIL", "")
APP_PASSWORD = os.environ.get("WATCH_APP_PASSWORD", "")  # Gmailアプリパスワード

STATE_FILE = "state.json"
TIMEOUT_SEC = 20
# =======================================


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
        return res.read().decode("utf-8", errors="ignore")


def extract_relevant(text: str) -> str:
    if not KEYWORDS:
        return text
    # キーワードが含まれる行だけを集める（簡易フィルタ）
    lines = text.splitlines()
    picked = [ln for ln in lines if any(k in ln for k in KEYWORDS)]
    return "\n".join(picked) if picked else ""


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
        raise RuntimeError("メール設定が未入力です（環境変数 WATCH_FROM_EMAIL / WATCH_TO_EMAIL / WATCH_APP_PASSWORD を設定してください）")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(FROM_EMAIL, APP_PASSWORD)
        server.send_message(msg)


def main():
    state = load_state()
    changes = []

    for url in WATCH_URLS:
        raw = fetch_text(url)
        relevant = extract_relevant(raw)
        h = sha256(relevant)

        old = state.get(url)
        if old is None:
            # 初回は記録だけ（通知しない）
            state[url] = h
            continue

        if h != old:
            changes.append(url)
            state[url] = h

    save_state(state)

    if changes:
        body = "硬式テニス関連ページに更新を検知しました。\n\n" + "\n".join(changes)
        send_mail(MAIL_SUBJECT, body)
        print("Updated:", changes)
    else:
        print("No change.")


if __name__ == "__main__":
    main()
