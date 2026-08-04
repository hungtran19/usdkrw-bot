name: Hourly Exchange Rate & Gold Checker

on:
  schedule:
    # Chạy vào phút thứ 0 của mỗi giờ (UTC)
    - cron: '0 * * * *'
  workflow_dispatch: # Nút bấm chạy thủ công trên GitHub

jobs:
  check-and-notify:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests

      - name: Run check script
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python main.py

      - name: Commit and push updated prices
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add last_prices.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "Chore: Update last prices [skip ci]" && git push)
