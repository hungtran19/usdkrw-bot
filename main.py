import os
import json
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
CHAT_ID = os.environ["CHAT_ID"].strip()

API_URL = "https://open.er-api.com/v6/latest/USD"

STATE_FILE = "state.json"
CHART_FILE = "chart.png"

TIMEZONE = "Asia/Seoul"

CHANGE_THRESHOLD = 2.0
ALERT_LEVEL = 1430.0
FORCE_SEND_INTERVAL = 24

# =========================
# LOGGER
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("usdkrw")


# =========================
# TIME
# =========================

def now():
    return datetime.now(
        ZoneInfo(TIMEZONE)
    )


# =========================
# STATE
# =========================

def load_state():

    if not Path(STATE_FILE).exists():

        return {
            "counter": 0,
            "history": []
        }

    with open(
        STATE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_state(state):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================
# DOWNLOAD RATE
# =========================

def get_rate():

    logger.info("Downloading exchange rate...")

    r = requests.get(
        API_URL,
        timeout=20
    )

    r.raise_for_status()

    data = r.json()["rates"]

    return {

        "usdkrw": float(data["KRW"]),

        "usdvnd": float(data["VND"]),

        "krwvnd": float(data["VND"]) / float(data["KRW"])

    }


# =========================
# HISTORY
# =========================

def add_history(state, rate):

    history = state.get("history", [])

    history.append({

        "time": now().isoformat(),

        "usdkrw": rate["usdkrw"],

        "usdvnd": rate["usdvnd"],

        "krwvnd": rate["krwvnd"]

    })

    # giữ tối đa 720 lần chạy
    history = history[-720:]

    state["history"] = history

    state["counter"] = state.get("counter", 0) + 1

    return history


def previous_record(history):

    if len(history) < 2:
        return None

    return history[-2]


def calc_change(current, previous):

    if previous is None:
        return None

    diff = current - previous

    pct = diff / previous * 100

    return {
        "diff": diff,
        "pct": pct
    }
	# =========================
# CHART
# =========================

def draw_chart(history):

    values = [x["usdkrw"] for x in history[-24:]]

    if len(values) < 2:
        return False

    plt.figure(figsize=(8, 4), dpi=140)

    plt.plot(
        values,
        linewidth=2,
        marker="o",
        markersize=4
    )

    plt.title("USD/KRW - Last 24 Runs")

    plt.xlabel("Run")

    plt.ylabel("KRW")

    plt.grid(alpha=0.3)

    plt.tight_layout()

    plt.savefig(CHART_FILE)

    plt.close()

    return True


# =========================
# FORMAT
# =========================

def arrow(change):

    if change is None:
        return "➖"

    if change["diff"] > 0:
        return "▲"

    if change["diff"] < 0:
        return "▼"

    return "➖"


# =========================
# MESSAGE
# =========================

def build_message(rate, change):

    lines = []

    lines.append("💵 USD Exchange Rate")
    lines.append("")

    lines.append(f"USD/KRW : {rate['usdkrw']:,.2f}")
    lines.append(f"USD/VND : {rate['usdvnd']:,.2f}")
    lines.append(f"KRW/VND : {rate['krwvnd']:.4f}")

    lines.append("")

    if change is None:

        lines.append("Previous : N/A")

    else:

        lines.append(
            f"Previous : {arrow(change)} "
            f"{change['diff']:+.2f} KRW "
            f"({change['pct']:+.2f}%)"
        )

    if rate["usdkrw"] >= ALERT_LEVEL:

        lines.append("")
        lines.append("🚨 ALERT")
        lines.append(
            f"USD/KRW >= {ALERT_LEVEL:.0f}"
        )

    lines.append("")
    lines.append(
        now().strftime("%Y-%m-%d %H:%M KST")
    )

    return "\n".join(lines)


# =========================
# SHOULD SEND
# =========================

def should_send(state, rate, change):

    if change is None:
        return True

    if rate["usdkrw"] >= ALERT_LEVEL:
        return True

    if abs(change["diff"]) >= CHANGE_THRESHOLD:
        return True

    if state["counter"] % FORCE_SEND_INTERVAL == 0:
        return True

    return False


# =========================
# TELEGRAM
# =========================

def telegram_url(method):

    return (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )


def send_text(message):

    r = requests.post(
        telegram_url("sendMessage"),
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=30
    )

    r.raise_for_status()


def send_photo(message):

    with open(CHART_FILE, "rb") as photo:

        r = requests.post(
            telegram_url("sendPhoto"),
            data={
                "chat_id": CHAT_ID,
                "caption": message
            },
            files={
                "photo": photo
            },
            timeout=30
        )

    r.raise_for_status()


def notify(rate, history, change):

    message = build_message(
        rate,
        change
    )

    if draw_chart(history):
        send_photo(message)
    else:
        send_text(message)
		# =========================
# MAIN
# =========================

def main():

    logger.info("=" * 60)

    state = load_state()

    rate = get_rate()

    history = add_history(
        state,
        rate
    )

    previous = previous_record(
        history
    )

    if previous is None:

        change = None

    else:

        change = calc_change(
            rate["usdkrw"],
            previous["usdkrw"]
        )

    save_state(state)

    if should_send(
        state,
        rate,
        change
    ):

        notify(
            rate,
            history,
            change
        )

        logger.info(
            "Telegram sent."
        )

    else:

        logger.info(
            "No significant change."
        )


if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        logger.exception(e)

        raise
		
