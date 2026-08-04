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
        print(f"Lỗi khi lấy tỷ giá ngoại tệ: {e}")
        return None, None

def get_sjc_gold_price():
    """Lấy giá vàng SJC bán ra (Đã xử lý sạch các ký tự đặc biệt của XML)"""
    try:
        url = "https://sjc.com.vn/xml/tygiagold.xml"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=10)
        
        # Xử lý các entity chưa định nghĩa trong XML SJC để tránh lỗi parser
        xml_text = res.content.decode('utf-8', errors='ignore')
        xml_clean = re.sub(r'&(?!(amp|lt|gt|quot|apos);)', '&amp;', xml_text)
        
        root = ET.fromstring(xml_clean)
        
        for item in root.findall(".//item"):
            buy_sell = item.attrib
            type_name = buy_sell.get("type", "")
            if "SJC" in type_name:
                sell_str = buy_sell.get("sell", "").replace(",", "").strip()
                if sell_str:
                    sell_price = float(sell_str) * 1000  # Đổi ra VND/lượng
                    return sell_price
    except Exception as e:
        print(f"Lỗi khi lấy giá vàng SJC: {e}")
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
    
    response = requests.post(url, json=payload, timeout=10)
    res_data = response.json()
    
    if res_data.get("ok"):
        print("✅ Đã gửi tin nhắn Telegram thành công!")
    else:
        print(f"❌ Lỗi gửi Telegram: {res_data.get('description')}")

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

    print("--- DỮ LIỆU HIỆN TẠI ---")
    print(f"USD/KRW : {krw}")
    print(f"USD/VND : {vnd}")
    print(f"Vàng SJC: {gold:,.0f} VND" if gold else "Vàng SJC: N/A")

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
