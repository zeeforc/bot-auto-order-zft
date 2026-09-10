#!/bin/bash

# Pastikan berada di direktori project
cd /home/container

echo "==================================="
echo "🚀 Memulai Setup Bot Auto Order..."
echo "==================================="

# 1. Setup GoPay Gateway (Node.js)
echo "📦 Menginstall dependencies GoPay Gateway..."
cd gopay-gateway
npm install
echo "▶️ Menjalankan GoPay Gateway di background..."
node server.js &
cd ..

# 2. Setup Telegram Bot (Python)
echo "🐍 Menginstall dependencies Python..."
# Verlang Terminal biasanya udah ada python3, kita pastikan venv dibuat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "▶️ Menjalankan Bot Telegram..."
python3 main.py
