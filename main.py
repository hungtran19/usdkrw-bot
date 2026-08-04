import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

url = "https://open.er-api.com/v6/latest/USD"

data = requests.get(url, timeout=20).json()

krw = data["rates"]["KRW"]
vnd = data["rates"]["VND"]

time = datetime.now(
    ZoneInfo("Asia/Seoul")
).strftime("%Y-%m-%d %H:%M KST")

message = f"""
💵 USD Exchange Rate

USD/KRW : {krw:,.2f}

USD/VND : {vnd:,.2f}

KRW/VND : {vnd/krw:.4f}

{time}
"""

requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={
        "chat_id": CHAT_ID,
        "text": message
    }
)
