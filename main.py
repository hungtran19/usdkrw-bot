import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
CHAT_ID = os.environ["CHAT_ID"].strip()

url = "https://open.er-api.com/v6/latest/USD"
r = requests.get(url, timeout=20)
r.raise_for_status()
data = r.json()["rates"]

krw = data["KRW"]
vnd = data["VND"]

msg = f"""💵 Exchange Rates

USD/KRW : {krw:,.2f}
USD/VND : {vnd:,.2f}
KRW/VND : {vnd/krw:.4f}

{datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")}
"""

resp = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": msg},
    timeout=20,
)
print(resp.status_code, resp.text)
resp.raise_for_status()
