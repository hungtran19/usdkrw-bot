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
    """
    Lấy giá vàng SJC Việt Nam (VND/lượng) 
    Sử dụng API tổng hợp dữ liệu giá vàng trong nước không bị chặn IP
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Nguồn 1: API Tỷ giá & Vàng tổng hợp công khai
    try:
        url = "https://vapi.vnappmob.com/api/v2/gold/sjc"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            results = data.get("results", [])
            if results:
                # Lấy giá bán ra SJC
                sell_val = float(results[0].get("sell", 0))
                if sell_val > 0:
                    return sell_val * 1000 if sell_val < 100000 else sell_val
    except Exception as e:
        print(f"⚠️ Nguồn 1 lỗi: {e}")

    # Nguồn 2 Dự phòng: API Giá vàng TyGia
    try:
        url = "https://api.statful.com/v1/gold/sjc"
        res = requests.get(url, headers=headers, timeout=10).json()
        if "price" in res:
            return float(res["price"])
    except Exception as e:
        print(f"⚠️ Nguồn 2 lỗi: {e}")

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
            print(f"❌ Lỗi Telegram: {res.get('description')}")
    except Exception as e:
        print(f"❌ Lỗi gửi tin nhắn Telegram: {e}")

def format_change(curr, prev, is_gold=False):
    """
    Sửa lỗi so sánh số thực: Làm tròn chênh lệch trước khi đánh giá TĂNG/GIẢM/KHÔNG ĐỔI
    """
    diff = curr - prev
    
    # Làm tròn để tránh lỗi số thực (floating point error)
    precision = 0 if is_gold else 2
    rounded_diff = round(diff, precision)

    pct = (diff / prev) * 100 if prev else 0

    if rounded_diff > 0:
        arrow = "⬆️ TĂNG"
        sign = "+"
    elif rounded_diff < 0:
        arrow = "⬇️ GIẢM"
        sign = ""
    else:
        arrow = "➡️ KHÔNG ĐỔI"
        sign = ""
    
    if is_gold:
        diff_str = f"{sign}{rounded_diff:,.0f}"
    else:
        diff_str = f"{sign}{rounded_diff:,.2f}"

    return arrow, diff_str, f"{sign}{pct:.2f}%"

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
    print("DỮ LIỆU CẬP NHẬT:")
    print(f"• USD/KRW : {krw}")
    print(f"• USD/VND : {vnd}")
    print(f"• Giá Vàng SJC: {gold:,.0f} VND/lượng" if gold else "• Giá Vàng SJC: Chưa lấy được")
    print("---------------------------------\n")

    for key, curr_val in current_prices.items():
        if curr_val is None:
            continue
        
        prev_val = last_prices.get(key)
        
        if prev_val is not None:
            diff = abs(curr_val - prev_val)
            threshold = THRESHOLDS.get(key, 0)

            # Chỉ đưa vào danh sách cảnh báo nếu chênh lệch >= ngưỡng
            if diff >= threshold:
                is_gold = "GOLD" in key
                arrow, diff_str, pct_str = format_change(curr_val, prev_val, is_gold=is_gold)
                unit = "VND" if "VND" in key or is_gold else "KRW"
                
                if is_gold:
                    curr_fmt = f"{curr_val:,.0f}"
                    prev_fmt = f"{prev_val:,.0f}"
                    display_name = "VÀNG SJC TRONG NƯỚC"
                else:
                    curr_fmt = f"{curr_val:,.2f}"
                    prev_fmt = f"{prev_val:,.2f}"
                    display_name = key

                alert_messages.append(
                    f"🔔 <b>CẢNH BÁO BIẾN ĐỘNG: {display_name}</b>\n"
                    f"• Giá hiện tại: <b>{curr_fmt} {unit}</b>\n"
                    f"• Giá trước đó: {prev_fmt} {unit}\n"
                    f"• Biến động: {arrow} <b>{diff_str} {unit}</b> ({pct_str})"
                )

    if alert_messages:
        full_msg = "🚨 <b>THÔNG BÁO TỶ GIÁ & GIÁ VÀNG HÀNG GIỜ</b> 🚨\n\n" + "\n\n".join(alert_messages)
        send_telegram_msg(full_msg)
    else:
        print("Không có mục nào biến động vượt ngưỡng cài đặt.")

    save_current_prices(current_prices)

if __name__ == "__main__":
    main()
