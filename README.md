# Bot Auto Order

Bot otomatis untuk mengelola order dan pembayaran menggunakan Telegram dan Tripay.

## Struktur Project

```
bot-auto-order/
├── config/
│   └── settings.py          # Konfigurasi env, token, api keys
├── app/
│   ├── core/
│   │   └── security.py      # Validasi callback, hashing, dll.
│   ├── domain/
│   │   ├── entities.py      # Enterprise business rules (User, Product, Order)
│   │   └── interfaces.py    # Abstract Repository / Abstraksi Database & Gateway
│   ├── infrastructure/
│   │   ├── database/
│   │   │   └── repository.py # Implementasi akses data (SQLAlchemy / Supabase)
│   │   └── payment/
│   │       └── tripay.py    # Tripay API Client (QRIS generation)
│   └── presentation/
│       ├── telegram/
│       │   ├── handlers/    # start.py, product.py, deposit.py, info.py
│       │   ├── keyboards/   # reply.py, inline.py (Dynamic layout generator)
│       │   └── states.py    # FSM States untuk input deposit & data
│       └── web/
│           └── callbacks.py # Webhook receiver untuk payment notification Tripay
├── main.py                  # Entry point aplikasi
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd bot-auto-order
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables

```bash
cp .env.example .env
# Edit .env dengan nilai yang sesuai
```

### 5. Run Application

```bash
python main.py
```

## Features

- 📦 **Product Management** - Listing dan detail produk
- 💳 **Deposit System** - Sistem deposit user dengan payment gateway Tripay
- 🧾 **Order Management** - Pembuatan dan tracking order
- 💬 **Telegram Bot** - Interface utama via Telegram
- 🔐 **Security** - Webhook verification dan payment validation
- 📊 **History** - Riwayat order dan transaksi

## Technology Stack

- **Framework**: Aiogram (Telegram), FastAPI (Web)
- **Database**: SQLAlchemy, Supabase
- **Payment**: Tripay API
- **Async**: asyncio
- **Security**: HMAC-SHA256

## API Endpoints

- `POST /webhooks/tripay/callback` - Payment callback dari Tripay
- `GET /webhooks/health` - Health check

## Development

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black .
```

### Linting

```bash
flake8
```

## License

MIT
