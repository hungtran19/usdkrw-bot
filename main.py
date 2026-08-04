import os
import json
import re
import requests
import xml.etree.ElementTree as ET

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
    """Lấy tỷ giá USD/KRW và USD/VND"""
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        res = requests.get(url, timeout=10).json()
        rates = res.get("rates", {})
        return rates.get("KRW"), rates.get("VND")
    except Exception as e:
        print(f"❌ Lỗi lấy tỷ giá ngoại tệ: {e}")
        return None, None

def get_sjc_gold_price():
    """Lấy giá vàng SJC bán ra (VND/lượng) từ các nguồn API ổn định hơn"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # --- NGUỒN 1: API Giá vàng Báo Mới / Giavang.org ---
    try:
        url = "https://giavang.org/api/v1/gold-prices/sjc"
        res = requests.get(url, headers=headers, timeout=10).json()
        if isinstance(res, list) and len(res) > 0:
            sell_price = float(res[0].get("sell", 0))
            if sell_price > 0:
                return sell_price * 1000 if sell_price < 100000 else sell_price
    except Exception as e:
        print(f"⚠️ Nguồn 1 (Giavang.org) chưa lấy được: {e}")

    # --- NGUỒN 2: API TyGiaVang / GiaVangNhanh ---
    try:
        url = "https://tygia.com/json.php?ran=1&rate=g"
        res = requests.get(url, headers=headers, timeout=10).text
        # Làm sạch chuỗi JSON trả về từ tygia.com
        res_json = json.loads(res.replace("(", "").replace(")", "").replace(";", ""))
        items = res_json.get("items", [])
        for item in items:
            if "SJC" in item.get("type", "").upper():
                sell_str = str(item.get("sell", "")).replace(",", "").replace(".", "")
                if sell_str.isdigit():
                    val = float(sell_str)
                    return val * 1000 if val < 1000000 else val
    except Exception as e:
        print(f"⚠️ Nguồn 2 (TyGia) chưa lấy được: {e}")

    # --- NGUỒN 3: Web Scraping từ TyGiaUSD / BTMC / MinhChau ---
    try:
        url = "https://tygiausd.com/gia-vang-sjc"
        res = requests.get(url, headers=headers, timeout=10)
        # Tìm chuỗi số biểu diễn giá bán SJC (ví dụ 89,500,000 hoặc 89.500)
        matches = re.findall(r'(\d{2,3}[,\.]\d{3}[,\.]\d{3})', res.text)
        if matches:
            clean_val = matches[0].replace(",", "").replace(".", "")
            return float(clean_val)
    except Exception as e:
        print(f"⚠️ Nguồn 3 (TygiaUSD) chưa lấy được: {e}")

    print("❌ Tất cả nguồn giá vàng SJC đều thất bại.")
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
        print("❌ CẢNH BÁO: Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID!")
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
            print(f"❌ Lỗi từ Telegram: {res.get('description')}")
    except Exception as e:
        print(f"❌ Lỗi kết nối Telegram: {e}")

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

    print("\n--- GIÁ CẬP NHẬT MỚI NHẤT ---")
    print(f"• USD/KRW : {krw}")
    print(f"• USD/VND : {vnd}")
    print(f"• Giá Vàng: {gold:,.0f} VND/lượng" if gold else "• Giá Vàng: N/A")
    print("-----------------------------\n")

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
                else:
                    curr_fmt = f"{curr_val:,.2f}"
                    prev_fmt = f"{prev_val:,.2f}"
                    diff_fmt = diff_str

                alert_messages.append(
                    f"🔔 <b>CẢNH BÁO BIẾN ĐỘNG: {key}</b>\n"
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
