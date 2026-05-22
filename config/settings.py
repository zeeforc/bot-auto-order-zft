"""
Configuration settings untuk Bot Auto Order
Konfigurasi env, token, api keys
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Tripay Configuration
TRIPAY_API_KEY = os.getenv("TRIPAY_API_KEY", "")
TRIPAY_API_SECRET = os.getenv("TRIPAY_API_SECRET", "")
TRIPAY_MERCHANT_CODE = os.getenv("TRIPAY_MERCHANT_CODE", "")

# Application Configuration
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Admin Configuration
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# Payment Configuration
QRIS_METHOD = os.getenv("QRIS_METHOD", "QRIS")  # Default: QRIS (no fee)
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "tripay")  # tripay / pakasir

# Pakasir Configuration
PAKASIR_BASE_URL = os.getenv("PAKASIR_BASE_URL", "https://app.pakasir.com")
PAKASIR_PROJECT_SLUG = os.getenv("PAKASIR_PROJECT_SLUG", "")
PAKASIR_API_KEY = os.getenv("PAKASIR_API_KEY", "")
PAKASIR_PAYMENT_METHOD = os.getenv("PAKASIR_PAYMENT_METHOD", "qris")

# Webhook Configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))


if not BOT_TOKEN:
    raise ValueError("Token Telegram bot tidak ditemukan! Pastikan sudah di-set di file .env")