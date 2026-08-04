import os
import json
import requests

# --- CẤU HÌNH THÔNG SỐ TELEGRAM ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_FILE = "last_prices.json"

# --- NGƯỠNG CẢNH BÁO ---
THRESHOLDS = {
    "USD/KRW": 0.0,         # Tăng/giảm >= 5 KRW
    "USD/VND": 000.0,       # Tăng/giảm >= 500 VND
    "GOLD_SJC": 000000.0    # Tăng/giảm >= 300,000 VND/lượng
}

def get_forex_rates():
    """Lấy tỷ giá ngoại tệ USD/KRW và USD/VND"""
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(url, timeout=10).json()
        rates = res.get("rates", {})
        return rates.get("KRW"), rates.get("VND")
    except Exception as e:
        print(f"❌ Lỗi lấy tỷ giá ngoại tệ: {e}")
        return None, None

def get_sjc_gold_price():
    """Lấy giá vàng SJC bán ra (VND/lượng) - Đã test hoạt động tốt"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Nguồn 1: WebGia SJC API (JSON trực tiếp)
    try:
        url = "https://api.webgia.com/v1/gold/sjc.json"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                # Lấy giá bán ra của mục đầu tiên
                sell_val = float(data[0].get("sell", 0))
                if sell_val > 0:
                    return sell_val * 1000 if sell_val < 100000 else sell_val
    except Exception as e:
        print(f"⚠️ Nguồn WebGia lỗi: {e}")

    # Nguồn 2 Dự phòng: API GiaVangOrg
    try:
        url = "https://giavang.org/api/v1/gold-prices/sjc"
        res = requests.get(url, headers=headers, timeout=10).json()
        if isinstance(res, list) and len(res) > 0:
            sell_val = float(res[0].get("sell", 0))
            if sell_val > 0:
                return sell_val * 1000 if sell_val < 100000 else sell_val
    except Exception as e:
        print(f"⚠️ Nguồn GiaVangOrg lỗi: {e}")

    return None

def load_last_prices():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_current_prices(prices):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=4, ensure_ascii=False)

def send_telegram_msg(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ CẢNH BÁO: Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID trong Secrets!")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10).json()
        if res.get("ok"):
            print("✅ Đã gửi tin nhắn Telegram thành công!")
        else:
            print(f"❌ Lỗi Telegram trả về: {res.get('description')}")
    except Exception as e:
        print(f"❌ Lỗi gửi tin nhắn Telegram: {e}")

def format_change(curr, prev):
    diff = curr - prev
    pct = (diff / prev) * 100 if prev else 0
    if diff > 0:
        arrow = "⬆️ TĂNG"
    elif diff < 0:
        arrow = "⬇️ GIẢM"
    else:
        arrow = "➡️ KHÔNG ĐỔI"
    
    sign = "+" if diff > 0 else ""
    return arrow, f"{sign}{diff:,.2f}", f"{sign}{pct:.2f}%"

def main():
    krw, vnd = get_forex_rates()
    gold = get_sjc_gold_price()

    current_prices = {
        "USD/KRW": krw,
        "USD/VND": vnd,
        "GOLD_SJC": gold
    }

    last_prices = load_last_prices()
    alert_messages = []

    print("\n---------------------------------")
    print("DỮ LIỆU LẤY THÀNH CÔNG THỰC TẾ:")
    print(f"• USD/KRW : {krw}")
    print(f"• USD/VND : {vnd}")
    print(f"• Giá Vàng SJC: {gold:,.0f} VND/lượng" if gold else "• Giá Vàng SJC: Thất bại")
    print("---------------------------------\n")

    for key, curr_val in current_prices.items():
        if curr_val is None:
            continue
        
        prev_val = last_prices.get(key)
        
        if prev_val is not None:
            diff = abs(curr_val - prev_val)
            threshold = THRESHOLDS.get(key, 0)

            if diff >= threshold:
                arrow, diff_str, pct_str = format_change(curr_val, prev_val)
                unit = "VND" if "VND" in key or "GOLD" in key else "KRW"
                
                if "GOLD" in key:
                    curr_fmt = f"{curr_val:,.0f}"
                    prev_fmt = f"{prev_val:,.0f}"
                    diff_fmt = f"{float(diff_str.replace(',','')):,.0f}"
                    display_name = "VÀNG SJC TRONG NƯỚC"
                else:
                    curr_fmt = f"{curr_val:,.2f}"
                    prev_fmt = f"{prev_val:,.2f}"
                    diff_fmt = diff_str
                    display_name = key

                alert_messages.append(
                    f"🔔 <b>CẢNH BÁO BIẾN ĐỘNG: {display_name}</b>\n"
                    f"• Giá hiện tại: <b>{curr_fmt} {unit}</b>\n"
                    f"• Giá trước đó: {prev_fmt} {unit}\n"
                    f"• Biến động: {arrow} <b>{diff_fmt} {unit}</b> ({pct_str})"
                )

    if alert_messages:
        full_msg = "🚨 <b>THÔNG BÁO TỶ GIÁ & GIÁ VÀNG HÀNG GIỜ</b> 🚨\n\n" + "\n\n".join(alert_messages)
        send_telegram_msg(full_msg)
    else:
        print("Biến động chưa vượt ngưỡng cài đặt.")

    save_current_prices(current_prices)

if __name__ == "__main__":
    main()
