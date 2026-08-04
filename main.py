import os
import json
import re
import requests
from bs4 import BeautifulSoup

# --- CẤU HÌNH THÔNG SỐ TELEGRAM ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_FILE = "last_prices.json"

# --- NGƯỠNG CẢNH BÁO ---
THRESHOLDS = {
    "USD/KRW": 5.0,         # Tăng/giảm >= 5 KRW
    "USD/VND": 500.0,       # Tăng/giảm >= 500 VND
    "GOLD_SJC": 300000.0    # Tăng/giảm >= 300,000 VND/lượng
}

def get_forex_rates():
    """Lấy tỷ giá USD/KRW và USD/VND từ Open ER API (Hoạt động 100%)"""
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
    Scrape giá vàng SJC bán ra (VND/lượng) trực tiếp từ HTML trang tin tức tài chính.
    Giúp vượt rào cản chặn IP/Bot của GitHub Actions.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    # Nguồn 1: Scrape từ trang Giá Vàng Báo Mới / Tin Tức
    try:
        url = "https://baomoi.com/tien-ich-gia-vang-sjc.epi"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Tìm thẻ chứa thông tin giá SJC
            rows = soup.find_all('tr')
            for row in rows:
                text = row.get_text()
                if "SJC" in text and ("1L" in text or "10L" in text or "Miếng" in text):
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        # Lấy cột bán ra
                        sell_str = cols[-1].get_text().strip().replace(',', '').replace('.', '')
                        digits = re.findall(r'\d+', sell_str)
                        if digits:
                            val = float(digits[0])
                            # Chuẩn hóa về đơn vị VND/Lượng (vd: 89500000)
                            if val < 100000:
                                return val * 1000
                            return val
    except Exception as e:
        print(f"⚠️ Nguồn Báo Mới thất bại: {e}")

    # Nguồn 2 Dự phòng: Scrape từ Giá Vàng ORG
    try:
        url = "https://giavang.org/"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Lấy giá bán SJC từ bảng tổng hợp
            text = soup.get_text()
            matches = re.findall(r'SJC[^\d]+(\d{2,3}[\.,]\d{3})', text)
            if matches:
                clean_num = matches[0].replace('.', '').replace(',', '')
                val = float(clean_num)
                return val * 1000 if val < 1000000 else val
    except Exception as e:
        print(f"⚠️ Nguồn GiaVangORG thất bại: {e}")

    print("❌ Không thể cào giá vàng SJC từ các nguồn HTML.")
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

def format_change(curr, prev, is_gold=False):
    """
    Sửa triệt để lỗi logic mũi tên khi giá không đổi:
    Sử dụng round() chính xác để tránh sai số dấu phẩy động của Python.
    """
    diff = curr - prev
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
    print("DỮ LIỆU LẤY VỀ:")
    print(f"• USD/KRW : {krw}")
    print(f"• USD/VND : {vnd}")
    print(f"• Giá Vàng SJC: {gold:,.0f} VND/lượng" if gold else "• Giá Vàng SJC: N/A (Thất bại)")
    print("---------------------------------\n")

    for key, curr_val in current_prices.items():
        if curr_val is None:
            continue
        
        prev_val = last_prices.get(key)
        
        if prev_val is not None:
            diff = abs(curr_val - prev_val)
            threshold = THRESHOLDS.get(key, 0)

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
        print("Biến động chưa vượt ngưỡng cài đặt.")

    save_current_prices(current_prices)

if __name__ == "__main__":
    main()
