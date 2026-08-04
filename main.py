import os, json, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

BOT_TOKEN=os.environ["BOT_TOKEN"]
CHAT_ID=os.environ["CHAT_ID"]

j=requests.get("https://open.er-api.com/v6/latest/USD",timeout=20).json()
krw=float(j["rates"]["KRW"])
vnd=float(j["rates"]["VND"])

state=Path("state.json")
prev=None
if state.exists():
    prev=json.loads(state.read_text()).get("krw")
state.write_text(json.dumps({"krw":krw}))

arrow="➖"; delta=0
if prev is not None:
    delta=krw-prev
    arrow="▲" if delta>0 else "▼" if delta<0 else "➖"

msg=f"""💵 Exchange Rates

USD/KRW: {krw:,.2f}
USD/VND: {vnd:,.2f}
KRW/VND: {vnd/krw:,.4f}

"""
if prev is not None:
    msg+=f"1h Change: {arrow} {delta:+.2f} KRW\n"
if krw>=1400:
    msg+="\n🚨 USD/KRW >= 1400\n"

msg+="Updated: "+datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")

requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
data={"chat_id":CHAT_ID,"text":msg},timeout=20).raise_for_status()
