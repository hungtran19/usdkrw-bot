import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
CHAT_ID = os.environ["CHAT_ID"].strip()

# Lấy tỷ giá
r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=20)
r.raise_for_status()

data = r.json()

print("API response:", data)

krw = data["rates"]["KRW"]
vnd = data["rates"]["VND"]

time = datetime.now(
    ZoneInfo("Asia/Seoul")
).strftime("%Y-%m-%d %H:%M KST")

message = f"""💵 USD Exchange Rate

USD/KRW: {krw:,.2f}

USD/VND: {vnd:,.2f}

KRW/VND: {vnd/krw:.4f}

{time}
"""

resp = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={
        "chat_id": CHAT_ID,
        "text": message,
    },
    timeout=20,
)

print("Telegram status:", resp.status_code)
print("Telegram response:", resp.text)

resp.raise_for_status()

print("Done!")
