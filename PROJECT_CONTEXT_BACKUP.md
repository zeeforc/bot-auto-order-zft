# 📦 PROJECT CONTEXT BACKUP — T-Store Auto Order Bot

> **Dokumentasi lengkap untuk handoff ke AI agent baru.**
> Tanggal backup: 21 Mei 2026
> Status: Active development, sandbox payment, belum production

---

## 1. Ringkasan Project

### Nama Project

**T-Store Auto Order Bot** (kadang disebut "ZFT Store" / `@zftstore_bot`)

### Tujuan Utama

Bot Telegram untuk otomatisasi penjualan produk digital (akun Netflix, Spotify, Canva, ChatGPT, dll) yang beroperasi 24/7. Owner cuma perlu input stok akun, sisanya bot yang handle:

- Tampilkan katalog produk
- Terima order dari user
- Generate QRIS untuk pembayaran
- Auto-deliver akun ke user setelah paid
- Notifikasi admin tiap transaksi

### Masalah yang Diselesaikan

- Owner store digital biasa kerja manual: chat user → cek pembayaran → kirim akun. Capek dan tidak scalable.
- Bot ini otomatisasi seluruh flow: order → payment → delivery, tanpa intervensi manual.
- Stok akun tersimpan di DB, otomatis berkurang saat user beli, otomatis terkirim.

### Target Pengguna

- **Owner/Admin (Telegram ID: `6405535980`)** — manage produk, stok, voucher, lihat report.
- **Customer (user biasa di Telegram)** — beli produk via saldo atau QRIS, terima akun otomatis.

### Platform

- **Telegram Bot** (frontend) — via `aiogram 3.x`
- **FastAPI Webhook Server** (backend untuk callback Tripay) — port 8080
- **Supabase PostgreSQL** (database) — via asyncpg
- **Tripay Payment Gateway** (QRIS) — sandbox saat ini, production setelah merchant approved

---

## 2. Tech Stack dan Dependencies

### Bahasa

- **Python 3.10+** (project ditest pake Python 3.14)

### Framework Utama

- **Aiogram 3.0.0** — async Telegram Bot framework
- **FastAPI 0.104.1** — webhook server untuk callback Tripay
- **asyncpg 0.31.0** — async PostgreSQL driver

### isi `requirements.txt`

```pip-requirements
# Telegram Bot Framework
aiogram==3.0.0
python-telegram-bot==20.0

# Web Framework
fastapi==0.104.1
uvicorn==0.24.0

# Database
sqlalchemy==2.0.23
supabase==2.0.0
asyncpg==0.31.0

# HTTP Client
httpx==0.25.0
requests==2.31.0

# QR Code Generation
qrcode[pil]>=7.0

# Excel Report
openpyxl>=3.1.0

# Configuration
python-dotenv==1.0.0
pydantic==2.4.2

# Security
cryptography==41.0.7

# Utilities
python-dateutil==2.8.2

# Development
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.11.0
flake8==6.1.0
```

### Penjelasan Package

| Package                     | Fungsi                 | Alasan                                                            |
| --------------------------- | ---------------------- | ----------------------------------------------------------------- |
| `aiogram==3.0.0`            | Telegram Bot framework | Async-first, modern API, FSM built-in                             |
| `fastapi==0.104.1`          | Webhook server         | Tripay callback handler (POST /webhook/tripay)                    |
| `uvicorn==0.24.0`           | ASGI server            | Run FastAPI app                                                   |
| `asyncpg==0.31.0`           | Async Postgres driver  | Atomic queries, race-condition safe, lebih cepat dari supabase-py |
| `httpx==0.25.0`             | Async HTTP client      | Call Tripay API                                                   |
| `qrcode[pil]>=7.0`          | Generate QR image      | Production: build QR dari EMV QRIS string                         |
| `openpyxl>=3.1.0`           | Generate Excel         | Export laporan transaksi                                          |
| `python-dotenv==1.0.0`      | Load .env              | Read credentials                                                  |
| `cryptography==41.0.7`      | HMAC                   | Verify Tripay callback signature                                  |
| `supabase==2.0.0`           | Supabase client        | **Tidak dipakai** — pakai asyncpg langsung. Bisa di-remove        |
| `python-telegram-bot==20.0` | (legacy)               | **Tidak dipakai** — bisa di-remove                                |
| `sqlalchemy==2.0.23`        | (legacy)               | **Tidak dipakai** — pakai asyncpg langsung                        |
| `requests==2.31.0`          | (legacy)               | **Tidak dipakai** — pakai httpx                                   |
| `pydantic==2.4.2`           | Validation             | Dipakai oleh FastAPI                                              |

---

## 3. Struktur Folder dan File

```
c:\bot-auto-order\
├── .env                          ← Konfigurasi environment (SECRETS)
├── .gitignore
├── main.py                       ← Entry point utama bot + webhook
├── seed_db.py                    ← Seed data produk awal ke DB
├── requirements.txt
├── README.md
├── AI_RULES.md                   ← Aturan untuk AI agent
├── PROGRESS.md                   ← Tracking progress development
├── TESTING_CHECKLIST.md          ← Checklist test untuk admin & user
├── CHECKLIST.md, TESTING_READY.md, IMPLEMENTATION_SUMMARY.md, WEBHOOK_TESTING_GUIDE.md, PHASE2_SUMMARY.md ← Docs lama
│
├── assets/
│   ├── banner_store.jpg          ← Banner saat /start
│   └── mock_qris.jpg             ← Mock QRIS image (sandbox)
│
├── config/
│   ├── __init__.py
│   └── settings.py               ← Load env vars: BOT_TOKEN, DB_URL, dll
│
├── migrations/                   ← SQL migrations
│   ├── 001_init_schema.sql       ← users, products, orders
│   ├── 002_vouchers.sql          ← vouchers, voucher_usages
│   ├── 003_account_stock.sql     ← account_stock (data akun per produk)
│   ├── 004_account_template.sql  ← Tambah kolom account_template di products
│   └── 005_product_variants.sql  ← product_variants + variant_id di account_stock & orders
│
└── app/                          ← Clean Architecture
    ├── __init__.py
    │
    ├── domain/                   ← Business rules (no external deps)
    │   ├── __init__.py
    │   ├── entities.py           ← Dataclasses: User, Product, Order, Voucher
    │   └── interfaces.py         ← ABC: ProductRepository, UserRepository, OrderRepository, VoucherRepository, PaymentGateway
    │
    ├── application/              ← Use cases / business logic
    │   ├── __init__.py
    │   └── services/
    │       ├── __init__.py
    │       ├── factory.py        ← Singleton factory: get_order_service(), get_deposit_service(), dll
    │       ├── order_service.py  ← OrderService.execute_order()
    │       ├── deposit_service.py← DepositService.create_deposit() & process_deposit_callback()
    │       ├── payment_service.py← PaymentService.process_order_payment() (webhook handler logic)
    │       ├── voucher_service.py← VoucherService.validate_voucher() & apply_voucher()
    │       └── delivery_service.py ← deliver_accounts() — auto-deliver akun ke user
    │
    ├── infrastructure/           ← External integrations
    │   ├── __init__.py
    │   ├── database/
    │   │   ├── __init__.py
    │   │   ├── connection.py     ← asyncpg pool init/close
    │   │   ├── factory.py        ← Singleton: get_product_repository(), get_user_repository(), get_order_repository(), get_voucher_repository()
    │   │   ├── product_repo.py   ← AsyncPgProductRepository + MockProductRepository
    │   │   ├── user_repo.py      ← AsyncPgUserRepository + MockUserRepository
    │   │   ├── order_repo.py     ← AsyncPgOrderRepository + MockOrderRepository
    │   │   ├── voucher_repo.py   ← AsyncPgVoucherRepository + MockVoucherRepository
    │   │   └── repository.py     ← (legacy/unused)
    │   └── payment/
    │       ├── __init__.py
    │       └── tripay.py         ← TripayClient (async, signature gen, callback verify)
    │
    ├── core/
    │   ├── __init__.py
    │   └── security.py           ← HMAC helper (legacy, tidak dipakai langsung)
    │
    └── presentation/
        ├── __init__.py
        ├── telegram/
        │   ├── __init__.py
        │   ├── states.py         ← FSM States (OrderStates, DepositStates, AddProductStates, dll)
        │   ├── handlers/
        │   │   ├── __init__.py
        │   │   ├── start.py      ← /start, pagination produk
        │   │   ├── menu.py       ← Reply keyboard buttons (List Produk, Voucher, dll) + handler angka produk + variant selection
        │   │   ├── order.py      ← Order flow: qty → checkout → catatan → konfirmasi → execute
        │   │   ├── deposit.py    ← Deposit saldo flow
        │   │   ├── voucher.py    ← /voucher CODE
        │   │   ├── info.py       ← /balance, /history, /cancel, /refund + refund reject
        │   │   ├── admin.py      ← SEMUA admin commands (~30 commands, ~2700 lines)
        │   │   └── product.py    ← (legacy/unused)
        │   └── keyboards/
        │       ├── __init__.py
        │       ├── reply.py      ← Main menu reply keyboard (3 col atas, 6 col angka, 3 col bawah)
        │       ├── inline.py     ← Pagination keyboard
        │       └── order.py      ← Product detail keyboard, note choice, confirmation
        └── web/
            ├── __init__.py
            └── callbacks.py      ← FastAPI app: POST /webhook/tripay + GET /health
```

### File Penting & Hubungannya

- **`main.py`** = entry point. Init bot + dispatcher, register routers, start polling + webhook server bersamaan.
- **`config/settings.py`** = load `.env` → exposed sebagai variables yang di-import di banyak tempat.
- **Domain** ← di-import oleh **Application** ← di-import oleh **Infrastructure & Presentation**. (Clean Architecture: dependency arrow ke dalam.)
- **`presentation/telegram/handlers/`** = handler-handler aiogram, di-register sebagai routers di `main.py`.
- **`presentation/web/callbacks.py`** = FastAPI app dijalankan paralel dengan bot polling.

---

## 4. Konfigurasi dan Environment Variable

### File `.env`

Lokasi: `c:\bot-auto-order\.env`

### Daftar Environment Variables

| Variable               | Fungsi                                                                              | Wajib?             | Contoh                                                                                  |
| ---------------------- | ----------------------------------------------------------------------------------- | ------------------ | --------------------------------------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`   | Token bot dari @BotFather                                                           | ✅                 | `1234567890:ABC...`                                                                     |
| `TELEGRAM_WEBHOOK_URL` | URL webhook Telegram (tidak dipakai, bot pakai polling)                             | ❌                 | (placeholder)                                                                           |
| `DATABASE_URL`         | Postgres DSN (Supabase Pooler URL)                                                  | ✅                 | `postgresql://postgres.xxx:pass@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres` |
| `SUPABASE_URL`         | Supabase project URL                                                                | ❌ (tidak dipakai) | `https://xxx.supabase.co`                                                               |
| `SUPABASE_KEY`         | Supabase publishable key                                                            | ❌ (tidak dipakai) | `sb_publishable_...`                                                                    |
| `TRIPAY_API_KEY`       | Tripay API key                                                                      | ✅ untuk QRIS      | `DEV-XXX...` (sandbox)                                                                  |
| `TRIPAY_API_SECRET`    | Tripay private key (untuk signature)                                                | ✅                 | `XXX-XXX-XXX`                                                                           |
| `TRIPAY_MERCHANT_CODE` | Tripay merchant code                                                                | ✅                 | `T50256`                                                                                |
| `QRIS_METHOD`          | QRIS method default                                                                 | ✅                 | `QRIS` (no fee), `QRIS2`, `QRISC`, `QRIS_SHOPEEPAY`                                     |
| `DEBUG`                | Flag debug mode                                                                     | ❌                 | `False`                                                                                 |
| `ENVIRONMENT`          | `development` atau `production` (dipakai Tripay untuk pilih sandbox/production URL) | ✅                 | `development`                                                                           |
| `ADMIN_IDS`            | Comma-separated Telegram IDs admin                                                  | ✅                 | `6405535980`                                                                            |
| `WEBHOOK_SECRET`       | HMAC key untuk verify Tripay callback (= TRIPAY_API_SECRET)                         | ✅                 | (sama dengan `TRIPAY_API_SECRET`)                                                       |
| `WEBHOOK_PORT`         | Port FastAPI webhook server                                                         | ❌                 | `8080`                                                                                  |

### Format `.env` Contoh (tanpa secret asli)

```dotenv
# Telegram Configuration
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook

# Database Configuration (Supabase Pooler URL — IPv4)
DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-1-REGION.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_KEY=sb_publishable_...

# Tripay Configuration
TRIPAY_API_KEY="DEV-XXX..."
TRIPAY_API_SECRET="XXX-XXX-XXX"
TRIPAY_MERCHANT_CODE="TXXXXX"
QRIS_METHOD=QRIS

# Application Configuration
DEBUG=False
ENVIRONMENT=development

# Admin Configuration (Telegram ID owner, comma-separated)
ADMIN_IDS=6405535980

# Webhook Configuration (sama dengan TRIPAY_API_SECRET)
WEBHOOK_SECRET=XXX-XXX-XXX
WEBHOOK_PORT=8080
```

### Catatan Konfigurasi Penting

- `DATABASE_URL` **HARUS** pakai **Supabase Pooler URL** (port 6543), bukan direct connection (port 5432). Ini penting karena AWS Pooler support IPv4, sedangkan direct connection cuma IPv6 di region tertentu.
- `WEBHOOK_SECRET` di-set sama dengan `TRIPAY_API_SECRET` karena Tripay pake private key untuk HMAC callback signature.
- `QRIS_METHOD=QRIS` adalah QRIS by ShopeePay (no fee). Method lain ada fee Rp 820.

---

## 5. Fitur Bot

### 5.1. /start (User & Admin)

- **Tujuan:** Entry point bot, tampilkan banner + list produk + reply keyboard
- **Akses:** Semua user
- **Input:** Command `/start`
- **Output:** Banner image + list 10 produk pertama (paginated) + reply keyboard utama
- **Alur:**
  1. `cmd_start()` di `start.py` dipanggil
  2. `user_repo.get_or_create()` — user di-register di DB kalau baru
  3. Fetch products (sorted by name ASC, limit 10)
  4. Kirim banner + caption list produk + inline pagination
  5. Kirim message kedua dengan reply keyboard utama
- **File:** `app/presentation/telegram/handlers/start.py`
- **Tabel DB:** `users` (auto-create), `products`, `product_variants`, `account_stock`
- **Status:** ✅ Selesai

### 5.2. List Produk + Pagination

- **Tujuan:** Tampilkan katalog produk
- **Akses:** Semua user
- **Trigger:** Tombol "📋 List Produk" atau pagination button
- **Output:** Format text:

  ```
  LIST PRODUCT

  [1]. ADOBE ( 95 )
  [2]. ALIGHT MOTION ( 350 )
  [3]. CANVA ( 927 )
  ...

  📄 Halaman 1 / 2
  📅 21 May 2026 02:30 AM
  ```

- **Catatan penting:**
  - Nomor `[1], [2], [3]` adalah **sequential index** (sorted by name ASC), BUKAN product ID database.
  - User tap angka → bot resolve sequential number → ambil produk ke-N dari sorted list.
- **File:** `start.py` (`format_product_list()`), `menu.py` (`handle_product_number()`)
- **Status:** ✅ Selesai

### 5.3. Variant Selection

- **Tujuan:** User pilih varian produk (misal Netflix 1 Bulan vs 2 Bulan)
- **Akses:** Semua user
- **Trigger:** User tap nomor produk yang punya variant
- **Output:**

  ```
  NETFLIX

  ➥ Stok Tersedia : 9
  ➥ Deskripsi : Netflix Premium Shared

  ➥ Variasi :
    ➯ NETFLIX 1P1U 1B - Rp 28,000 (4)
    ➯ NETFLIX 1P2U 1B - Rp 17,000 (5)

  📅 21 May 2026 06:30
  Pilih variasi di bawah:
  [NETFLIX 1P1U 1B (4)]
  [NETFLIX 1P2U 1B (5)]
  ```

- **File:** `menu.py` (`handle_product_number()`, `handle_variant_selection()`)
- **Status:** ✅ Selesai

### 5.4. Order Flow

- **Akses:** Semua user
- **Tujuan:** Beli produk via Saldo atau QRIS
- **Alur lengkap:**
  1. User pilih variant → detail variant + qty selector + tombol Buy(Saldo)/Buy(Now)
  2. Tap +/- → qty update (anti-overflow stock check)
  3. Tap Buy → pilih catatan (Isi/Skip)
  4. Konfirmasi → execute_order
  5. **Saldo:** langsung paid → deliver akun otomatis → kirim 2 pesan (detail transaksi + delivery_description)
  6. **QRIS:** generate via Tripay → kirim QR/checkout link → tunggu callback → setelah paid → deliver akun
- **FSM States:** `OrderStates` (`waiting_for_qty_or_checkout`, `waiting_for_note_choice`, `waiting_for_note_text`, `waiting_for_confirmation`)
- **File:** `order.py`, `keyboards/order.py`
- **Anti-double-click:** flag `_processing` di state
- **Status:** ✅ Selesai

### 5.5. QRIS Payment

- **Trigger:** User pilih "Buy (Now)" → konfirmasi
- **Alur:**
  1. Order dibuat (status=pending)
  2. Call `tripay.create_order_payment()` → dapat `qr_string`, `qr_url`, `checkout_url`, `reference`
  3. Sandbox mode (`qr_string` = "SANDBOX MODE"): tampilkan text + checkout link saja
  4. Production mode: generate QR image dari `qr_string` (EMV QRIS) pakai library `qrcode`, kirim sebagai `BufferedInputFile`
  5. Tampilkan tombol "❌ Batalkan Pembayaran"
  6. Schedule `_auto_expire_qris` task — auto-cancel order + delete pesan setelah 15 menit
- **File:** `order.py`, `tripay.py`, `callbacks.py` (webhook)
- **Status:** ✅ Selesai (sandbox), ⏳ menunggu merchant Tripay approved untuk production

### 5.6. Webhook Tripay (Auto-update payment status)

- **Endpoint:** `POST /webhook/tripay` (FastAPI di port 8080)
- **Alur:**
  1. Tripay POST callback dengan body JSON (reference, merchant_ref, status, amount, paid_at)
  2. Verify signature HMAC-SHA256 (`X-Callback-Signature` header vs HMAC dari body pakai `TRIPAY_API_SECRET`)
  3. Parse `merchant_ref`:
     - Prefix `DEP-` → deposit callback → add balance ke user → notif user
     - Else → order callback → update order status → deliver akun → notif user + admin
  4. Return 200 OK (wajib, biar Tripay ga retry)
- **File:** `app/presentation/web/callbacks.py`
- **Status:** ✅ Selesai

### 5.7. Auto-Deliver Akun

- **Tujuan:** Setelah order paid, otomatis ambil akun dari `account_stock`, mark used, kirim ke user
- **Alur:**
  1. Order status = paid
  2. `deliver_accounts(order_id, product_id, quantity, user_id, variant_id)` dipanggil
  3. Query `account_stock WHERE variant_id = X AND is_used = FALSE LIMIT N FOR UPDATE SKIP LOCKED` (atomic, race-safe)
  4. Mark akun `is_used = TRUE`, simpan `used_by`, `order_id`, `used_at`
  5. Update stock variant + parent (sync dari count account_stock)
  6. Format akun pakai template (variant.account_template > product.account_template)
  7. Return formatted text → ditampilkan di pesan delivery
- **File:** `app/application/services/delivery_service.py`
- **Format akun:** `email|password|profile|pin` → display `Email : x\nPassword : y\nProfile : z\nPIN : 1234`
- **Status:** ✅ Selesai

### 5.8. Deskripsi 3-Tier

| Field                  | Tabel                           | Tampil di                                   | Kapan dipakai                                   |
| ---------------------- | ------------------------------- | ------------------------------------------- | ----------------------------------------------- |
| `short_description`    | `products`                      | List produk overview                        | User tap nomor produk induk                     |
| `description`          | `product_variants`              | Detail variant                              | User pilih variant                              |
| `delivery_description` | `products` + `product_variants` | Pesan setelah paid (T&C, syarat login, dll) | Setelah order paid (variant > product fallback) |

- **Logic delivery:**
  ```
  variant.delivery_description ada? → pakai itu
  ↓ kosong
  product.delivery_description ada? → pakai itu
  ↓ kosong
  Skip pesan 2 (cuma kirim pesan detail transaksi)
  ```
- **Edit via:** `/editproduct` atau `/editvariant` → pilih field
- **Status:** ✅ Selesai

### 5.9. Voucher System

- **Akses:** User pakai `/voucher CODE`, admin manage via `/addvoucher`, `/listvoucher`, `/delvoucher`
- **Discount type:** `fixed` (Rp) atau `percent` (%) dengan optional max_discount
- **Constraints:** `min_purchase`, `max_usage`, `expired_at`, 1 voucher per user
- **Tabel DB:** `vouchers`, `voucher_usages`
- **File:** `voucher_service.py`, `voucher_repo.py`, `handlers/voucher.py`
- **Status:** ✅ Backend selesai. ⚠️ **Belum integrate ke order checkout flow** — voucher belum ke-apply otomatis saat order, baru bisa di-check via `/voucher CODE`.

### 5.10. Saldo / Deposit

- **Akses:** Semua user
- **Alur deposit:**
  1. Tombol "💰 Deposit" → pilih nominal (preset 10k-500k atau ketik manual)
  2. Konfirmasi → call Tripay `create_qris_deposit()` → dapat QRIS
  3. User bayar → webhook callback → balance auto-add → notif user
- **Alur pakai saldo:** Pilih "Buy (Saldo)" di order → balance dikurangi atomic (`UPDATE users SET balance = balance - $2 WHERE balance >= $2`)
- **File:** `deposit.py`, `deposit_service.py`
- **Status:** ✅ Selesai

### 5.11. User Commands

| Command                   | Fungsi                                                                    | Status |
| ------------------------- | ------------------------------------------------------------------------- | ------ |
| `/balance`                | Cek saldo                                                                 | ✅     |
| `/history`                | Riwayat order (paginated 5/page)                                          | ✅     |
| `/cancel ORDER_ID`        | Cancel order pending (support partial 8-char ID)                          | ✅     |
| `/refund ORDER_ID ALASAN` | Request refund (paid only, wajib alasan, notif admin dengan tombol Tolak) | ✅     |
| `/voucher CODE`           | Cek info voucher                                                          | ✅     |

### 5.12. Admin Commands (~30 commands)

#### Payment & Webhook

- `/admin` — menu admin (list semua command)
- `/setqris` — ganti QRIS method (runtime, tanpa restart) — pilih dari 4 method
- `/getqris` — lihat method aktif
- `/testwebhook ORDER_ID` — simulasi callback PAID (untuk test tanpa ngrok)
- `/webhookinfo` — info webhook URL untuk setup ngrok

#### Product Management

- `/listproduct` — list semua produk + ID
- `/addproduct` — interactive 5-step (nama, deskripsi, kategori, harga, stok)
- `/editproduct` — interactive: ID → field → value (dengan tombol Back)
- `/delproduct` — interactive: ID → konfirmasi (soft delete)
- `/restock ID QTY` — quick add/remove stock (one-liner, +/- value)
- `/bulkadd` — paste multi-line untuk add banyak produk sekaligus
- `/bulkdel product 1,5,7` — bulk delete

#### Variant Management

- `/addvariant ID` — interactive 4-step (nama, kode, deskripsi, harga)
- `/editvariant ID` — interactive: pilih variant → field → value
- `/delvariant ID` — interactive: pilih variant → konfirmasi
- `/listvariant ID` — list variant per produk
- `/bulkdel variant 1,2,3` — bulk delete variant

#### Account Stock

- `/addstock ID` — interactive: pilih variant → paste data akun (1 baris per akun)
- `/viewstock ID` — lihat jumlah stok akun (available + used)
- `/stockall` — summary stok semua produk
- `/settemplate ID Email|Password|...` — set template format akun
- `/bulkdel stock 5` — hapus semua akun unused di produk ID 5
- `/bulkdel stockvar 3` — hapus semua akun unused di variant ID 3

#### User Management

- `/banuser USER_ID` — ban user (set `is_banned = TRUE`)
- `/unbanuser USER_ID` — unban
- `/broadcast PESAN` — kirim pesan ke semua user non-banned

#### Voucher Management

- `/addvoucher CODE TYPE VALUE [MAX_USAGE] [MIN_PURCHASE]`
- `/listvoucher`
- `/delvoucher ID`

#### Analytics

- `/report [daily|weekly|monthly]` — laporan + tombol "Detail Transaksi" + "Download Excel"
- `/topproducts [limit]` — produk terlaris by paid orders
- `/topusers [limit]` — top spender
- `/stats` — statistik bot (jumlah produk aktif, QRIS method, env)

---

## 6. Alur Kerja Bot Secara Keseluruhan

### Saat Bot Dijalankan (`python main.py`)

1. `main.py` di-execute → `asyncio.run(main())`
2. `main()` jalankan 3 task paralel via `asyncio.gather()`:
   - `run_bot()` — aiogram polling
   - `run_webhook_server()` — uvicorn FastAPI
   - `_cleanup_stale_orders()` — background task setiap 30 menit
3. `run_bot()`:
   - Init `Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))`
   - Init `Dispatcher()`
   - Register lifecycle hooks `dp.startup.register(on_startup)`, `dp.shutdown.register(on_shutdown)`
   - **Register routers urut (penting!):** admin → info → start → voucher → deposit → order → menu (catch-all paling akhir)
   - Inject bot ke webhook handler via `set_bot(bot)`
   - Register bot commands per scope:
     - User scope (default): start, balance, history, voucher, cancel, refund
     - Admin scope (per chat ID): semua ~33 commands
   - Start polling
4. `on_startup()` jalan: cek koneksi DB
5. Bot ready, log: `🚀 Bot siap! Kirim /start di Telegram.`

### Routing Handler

- aiogram routes message ke router pertama yang match.
- **Order penting:** routers spesifik dulu (admin, info, start), lalu generic (menu catch-all).
- Setiap router pakai filter (`Command(...)`, `F.text == "..."`, `F.data.startswith("...")`, FSM state filter).

### Alur User (Beli Produk)

1. User kirim `/start` → bot reply banner + list produk + reply keyboard
2. User tap nomor "3" → `handle_product_number()` di `menu.py`
3. Bot resolve nomor 3 → produk ke-3 (sorted by name) → check variant
4. Jika ada variant: tampilkan list variant + tombol per variant
5. User tap variant → `handle_variant_selection()` → simpan `product_data` di FSM, set state `OrderStates.waiting_for_qty_or_checkout`, kirim detail variant + qty selector
6. User tap +/- untuk adjust qty → `handle_qty_change()` update caption
7. User tap "Buy(Saldo)" atau "Buy(Now)" → `handle_checkout_method()` → simpan method, set state `waiting_for_note_choice`, tampilkan tombol catatan
8. User pilih catatan (Isi/Skip) → `process_note_text()` atau `skip_note()` → `render_confirmation_screen()`
9. User tap "✅ Konfirmasi" → `execute_order()`:
   - Anti-double-click check (flag `_processing`)
   - Capture data dari FSM state, lalu `state.clear()`
   - **Saldo path:**
     - `OrderService.execute_order(payment_method="saldo", variant_id=X, unit_price=Y)`
     - Validate stok + balance (atomic deduct)
     - Create order (status=paid)
     - `deliver_accounts()` — ambil akun dari pool
     - Kirim 2 pesan: detail transaksi + delivery_description
     - Notify admin + delivered accounts
     - Cleanup pesan flow sebelumnya (variant detail, catatan, konfirmasi)
   - **QRIS path:**
     - `execute_order(payment_method="now")` → status=pending
     - Call Tripay `create_order_payment()` → dapat reference, qr_string, qr_url, checkout_url
     - Tampilkan QR/checkout link + cancel button
     - Schedule auto-expire 15 menit
     - Tunggu webhook callback dari Tripay

### Alur Admin (Tambah Produk + Restock Akun)

1. `/listproduct` → cek ID produk induk yang ada
2. `/addvariant 5` → bot tanya: nama, kode, deskripsi, harga (4 step) → konfirmasi → variant tersimpan
3. `/settemplate 5 Email|Password|Profile|PIN` → set template untuk produk Netflix (ID 5)
4. `/addstock 5` → bot tampilkan list variant Netflix → admin pilih variant
5. Admin paste multi-line akun (format sesuai template):
   ```
   email1@gmail.com|Pass123|Profile 1|1234
   email2@gmail.com|Pass456|Profile 2|5678
   ```
6. Bot insert ke `account_stock`, sync stock variant + parent
7. Tombol "🔙 Kembali ke Variant" → bisa add ke variant lain tanpa ketik command lagi

### Webhook Callback Flow (QRIS Paid)

1. User bayar QRIS via e-wallet → Tripay terima
2. Tripay POST ke `https://YOUR_NGROK_URL/webhook/tripay` dengan body JSON + header `X-Callback-Signature`
3. `tripay_webhook()` di `callbacks.py`:
   - Verify HMAC signature
   - Parse merchant_ref → tentukan deposit atau order
   - **Order callback:**
     - `payment_service.process_order_payment()` — update status pending → paid
     - Update payment_ref di order
     - `deliver_accounts(variant_id=order.variant_id)` — ambil akun
     - Kirim 2 pesan ke user: detail transaksi + delivery_description
     - Kirim notif admin (dengan delivered accounts)
4. Return 200 OK ke Tripay

---

## 7. Database

### DB yang dipakai

- **Supabase PostgreSQL** (production)
- **Mock in-memory dict** (fallback otomatis jika DB ga reachable saat startup)

### Library

- **asyncpg 0.31.0** — async driver, support `FOR UPDATE SKIP LOCKED` untuk concurrent stock fetch
- **statement_cache_size=0** — wajib karena Supabase Pooler (PgBouncer) tidak support prepared statements

### Struktur Tabel

#### `users`

| Field                              | Type                           | Keterangan       |
| ---------------------------------- | ------------------------------ | ---------------- |
| `telegram_id`                      | BIGINT PK                      | Telegram user ID |
| `username`                         | VARCHAR(64)                    | nullable         |
| `first_name`, `last_name`, `phone` | VARCHAR                        | nullable         |
| `balance`                          | BIGINT NOT NULL DEFAULT 0      | IDR (CHECK >= 0) |
| `is_banned`                        | BOOLEAN NOT NULL DEFAULT FALSE |                  |
| `created_at`, `updated_at`         | TIMESTAMPTZ                    |                  |

#### `products` (produk induk / kategori)

| Field                      | Type                          | Keterangan                                           |
| -------------------------- | ----------------------------- | ---------------------------------------------------- | -------- | ---- |
| `id`                       | BIGSERIAL PK                  |                                                      |
| `name`                     | VARCHAR(128) NOT NULL         | "CANVA", "NETFLIX", dll                              |
| `description`              | TEXT                          | (legacy, sometimes long)                             |
| `short_description`        | TEXT                          | Untuk overview list                                  |
| `delivery_description`     | TEXT                          | Untuk pesan setelah paid                             |
| `category`                 | VARCHAR(64)                   | streaming, software, design, ai, productivity        |
| `price`                    | BIGINT NOT NULL               | IDR (legacy, dipakai kalau no variant)               |
| `stock`                    | INTEGER NOT NULL DEFAULT 0    | (sekarang dihitung dynamic dari account_stock count) |
| `is_active`                | BOOLEAN NOT NULL DEFAULT TRUE |                                                      |
| `account_template`         | TEXT                          | "Email                                               | Password | ..." |
| `created_at`, `updated_at` | TIMESTAMPTZ                   |                                                      |

#### `product_variants` (varian per produk)

| Field                      | Type                                       | Keterangan                               |
| -------------------------- | ------------------------------------------ | ---------------------------------------- |
| `id`                       | BIGSERIAL PK                               |                                          |
| `product_id`               | BIGINT FK → products(id) ON DELETE CASCADE |                                          |
| `name`                     | VARCHAR(128)                               | "NETFLIX 1P1U 1B"                        |
| `code`                     | VARCHAR(32)                                | "nf1p1u"                                 |
| `description`              | TEXT                                       | Deskripsi singkat variant                |
| `delivery_description`     | TEXT                                       | T&C untuk variant ini (override product) |
| `price`                    | BIGINT                                     | IDR per variant                          |
| `stock`                    | INTEGER                                    | (sync dari account_stock count)          |
| `is_active`                | BOOLEAN                                    |                                          |
| `account_template`         | TEXT                                       | Template per variant (override product)  |
| `created_at`, `updated_at` | TIMESTAMPTZ                                |                                          |

#### `orders`

| Field                      | Type                                    | Keterangan                                              |
| -------------------------- | --------------------------------------- | ------------------------------------------------------- |
| `id`                       | VARCHAR(64) PK                          | UUID generated di app                                   |
| `user_id`                  | BIGINT FK → users                       |                                                         |
| `product_id`               | BIGINT FK → products ON DELETE RESTRICT |                                                         |
| `variant_id`               | BIGINT FK → product_variants            | nullable                                                |
| `quantity`                 | INTEGER (>0)                            |                                                         |
| `total_price`              | BIGINT (>=0)                            | IDR                                                     |
| `status`                   | VARCHAR(32)                             | CHECK in (pending, paid, shipped, delivered, cancelled) |
| `payment_method`           | VARCHAR(32)                             | saldo, now, qris                                        |
| `payment_ref`              | VARCHAR(128)                            | Tripay reference                                        |
| `created_at`, `updated_at` | TIMESTAMPTZ                             |                                                         |

#### `account_stock` (data akun digital)

| Field                   | Type                                   | Keterangan                  |
| ----------------------- | -------------------------------------- | --------------------------- |
| `id`                    | BIGSERIAL PK                           |                             |
| `product_id`            | BIGINT FK → products ON DELETE CASCADE |                             |
| `variant_id`            | BIGINT FK → product_variants           | nullable                    |
| `account_data`          | TEXT NOT NULL                          | "email\|pass\|profile\|pin" |
| `is_used`               | BOOLEAN DEFAULT FALSE                  |                             |
| `used_by`               | BIGINT FK → users(telegram_id)         |                             |
| `order_id`              | VARCHAR(64) FK → orders(id)            |                             |
| `created_at`, `used_at` | TIMESTAMPTZ                            |                             |

#### `vouchers`

| Field            | Type               | Keterangan                         |
| ---------------- | ------------------ | ---------------------------------- |
| `id`             | BIGSERIAL PK       |                                    |
| `code`           | VARCHAR(32) UNIQUE | uppercase saat di-store            |
| `discount_type`  | VARCHAR(16)        | CHECK in (fixed, percent)          |
| `discount_value` | BIGINT             | IDR (fixed) atau % (percent)       |
| `min_purchase`   | BIGINT             | IDR                                |
| `max_discount`   | BIGINT             | nullable, untuk cap diskon percent |
| `max_usage`      | INTEGER            | total kuota                        |
| `used_count`     | INTEGER            |                                    |
| `is_active`      | BOOLEAN            |                                    |
| `expired_at`     | TIMESTAMPTZ        | nullable                           |

#### `voucher_usages` (1 voucher per user)

| Field                       | Type         | Keterangan         |
| --------------------------- | ------------ | ------------------ |
| `id`                        | BIGSERIAL PK |                    |
| `voucher_id`                | BIGINT FK    |                    |
| `user_id`                   | BIGINT       |                    |
| `order_id`                  | VARCHAR(64)  |                    |
| `used_at`                   | TIMESTAMPTZ  |                    |
| UNIQUE(voucher_id, user_id) |              | Prevent double use |

### Atomic Operations Penting

1. **Stock decrement (legacy, sekarang ga dipakai):**
   ```sql
   UPDATE products SET stock = stock - $2
   WHERE id = $1 AND is_active = TRUE AND stock >= $2 RETURNING id;
   ```
2. **Balance deduct:**
   ```sql
   UPDATE users SET balance = balance - $2
   WHERE telegram_id = $1 AND NOT is_banned AND balance >= $2 RETURNING telegram_id;
   ```
3. **Account fetch (concurrent-safe):**
   ```sql
   SELECT id, account_data FROM account_stock
   WHERE variant_id = $1 AND is_used = FALSE
   ORDER BY id ASC LIMIT $2 FOR UPDATE SKIP LOCKED;
   ```
4. **Voucher increment:**
   ```sql
   UPDATE vouchers SET used_count = used_count + 1
   WHERE id = $1 AND is_active = TRUE AND used_count < max_usage RETURNING id;
   ```

### Setup Database dari Awal

```bash
# 1. Connect ke Supabase via psql / SQL editor
# 2. Run migrations berurutan:
psql $DATABASE_URL -f migrations/001_init_schema.sql
psql $DATABASE_URL -f migrations/002_vouchers.sql
psql $DATABASE_URL -f migrations/003_account_stock.sql
psql $DATABASE_URL -f migrations/004_account_template.sql
psql $DATABASE_URL -f migrations/005_product_variants.sql

# Atau via Supabase dashboard → SQL Editor → paste & run

# 3. Seed initial products (optional, gunakan seed_db.py)
python seed_db.py
```

---

## 8. API dan Integrasi Eksternal

### Tripay Payment Gateway

- **URLs:**
  - Sandbox: `https://tripay.co.id/api-sandbox`
  - Production: `https://tripay.co.id/api`
- **Auth:** `Authorization: Bearer {API_KEY}`
- **Endpoint utama:**
  - `POST /transaction/create` — generate QRIS
  - `GET /transaction/detail?reference=xxx` — cek status
- **Signature untuk create:** `HMAC-SHA256(private_key, merchant_code + merchant_ref + amount)`
- **Signature untuk callback verify:** `HMAC-SHA256(private_key, raw_body)` — value ada di header `X-Callback-Signature`

#### Format Request `create_order_payment`

```json
{
  "method": "QRIS",
  "merchant_ref": "ORDER_UUID",
  "amount": 28000,
  "customer_name": "User 6405535980",
  "customer_email": "user6405535980@tstore.bot",
  "customer_phone": "08000000000",
  "order_items": [{ "name": "NETFLIX", "price": 28000, "quantity": 1 }],
  "expired_time": 1779211086,
  "signature": "hmac_hex"
}
```

#### Format Response (sandbox)

```json
{
  "reference": "DEV-T50256371016VBRER",
  "merchant_ref": "ORDER_UUID",
  "checkout_url": "https://tripay.co.id/checkout/DEV-...",
  "qr_url": "https://tripay.co.id/qr/DEV-...",
  "qr_string": "SANDBOX MODE",
  "amount": 28000,
  "fee": 0,
  "total_amount": 27854,
  "expired_time": 1779211086,
  "status": "UNPAID"
}
```

⚠️ **Penting:** Di sandbox, `qr_string` selalu `"SANDBOX MODE"` (placeholder, bukan EMV QRIS asli). Di production, `qr_string` akan berisi EMV QRIS string panjang yang bisa di-scan langsung oleh e-wallet.

### Telegram Bot API

- Via aiogram framework, polling mode (bukan webhook)
- Bot Token dari @BotFather
- Commands di-register per scope (default vs admin chat) via `bot.set_my_commands()`

---

## 9. Sistem Pembayaran / Transaksi

### Payment Methods

1. **Saldo (Balance)** — instant paid, langsung deliver akun
2. **QRIS via Tripay** — pending, paid setelah callback dari Tripay

### QRIS Methods (di `/setqris`)

| Code             | Nama                  | Fee           |
| ---------------- | --------------------- | ------------- |
| `QRIS`           | QRIS by ShopeePay     | Rp 0 (no fee) |
| `QRIS2`          | QRIS Standard         | ~Rp 820       |
| `QRISC`          | QRIS Customizable     | ~Rp 820       |
| `QRIS_SHOPEEPAY` | QRIS Custom ShopeePay | Rp 0 (no fee) |

### Status Transaksi

| Status      | Arti                                                        |
| ----------- | ----------------------------------------------------------- |
| `pending`   | Belum dibayar (QRIS waiting) atau saldo flow belum complete |
| `paid`      | Sukses bayar                                                |
| `shipped`   | (legacy, ga dipakai)                                        |
| `delivered` | (legacy, ga dipakai)                                        |
| `cancelled` | User cancel atau auto-expire                                |
| `refunded`  | (mapping dari Tripay status REFUND)                         |

### Auto-Expire QRIS

- 15 menit setelah QRIS di-generate
- Background asyncio task (`_auto_expire_qris`) hapus pesan QRIS + cancel order
- Backup: `_cleanup_stale_orders()` di main.py jalan setiap 30 menit, cancel semua order pending > 30 menit

### Refund Flow

1. User: `/refund ORDER_ID ALASAN` (wajib alasan, support partial 8-char ID)
2. Validasi: order milik user, status = paid
3. Notif admin dengan tombol "❌ Tolak Refund"
4. Admin tap tombol → input alasan penolakan → bot kirim ke user
5. Approve: admin manual (kirim saldo via /addbalance — **belum ada command ini**, perlu ditambah)

### File Pembayaran

- `app/infrastructure/payment/tripay.py` — TripayClient
- `app/application/services/deposit_service.py` — DepositService
- `app/application/services/payment_service.py` — PaymentService (webhook logic)
- `app/presentation/web/callbacks.py` — FastAPI webhook endpoint
- `app/presentation/telegram/handlers/order.py` — Order flow + QRIS display
- `app/presentation/telegram/handlers/deposit.py` — Deposit flow

---

## 10. Sistem Admin

### Cara Verifikasi Admin

- Telegram ID dicek vs `ADMIN_IDS` env variable
- Function helper: `_is_admin(user_id) -> bool` di `admin.py`
- Setiap admin command panggil `_is_admin()` di awal — kalau bukan admin, return silent

### Hak Akses Admin

- Akses semua command admin di popup `/`
- Set bot commands per chat scope: admin lihat ~33 commands, user biasa cuma 6 commands
- Tidak bisa di-ban (`/banuser` reject jika target adalah admin)

### Fitur Admin (lihat section 5.12 untuk daftar lengkap)

- Product CRUD (interactive FSM)
- Variant CRUD (interactive FSM)
- Account stock management (per variant)
- Voucher CRUD
- User ban/unban
- Broadcast message
- Analytics & report (Excel export)
- Webhook testing simulator
- Bulk delete operations
- QRIS method switcher (runtime)

### Notifikasi Admin

Setiap order paid (saldo atau QRIS), admin auto-receive:

```
🔔 ORDER PAID

Kode : a679395d
Produk : NETFLIX
Jumlah : 1
Total : Rp 28,000
Customer : @username
Tanggal : 21/05/2026 06:30

📦 Akun terkirim:
Email : netflix@gmail.com
Password : Pass123
Profile : Profile 3
PIN : 1234
```

---

## 11. Sistem User

### Alur User Baru

1. User cari bot di Telegram → tap "Start" / kirim `/start`
2. `cmd_start()` → `user_repo.get_or_create(telegram_id)` → record di-insert ke `users` dengan balance=0
3. Bot kirim banner + list produk + reply keyboard
4. User browse produk, beli, dll

### Data User Tersimpan

| Field         | Source                                                        |
| ------------- | ------------------------------------------------------------- |
| `telegram_id` | Auto dari Telegram                                            |
| `username`    | (tidak auto-update, perlu manual update saat order kalau mau) |
| `balance`     | Default 0, bertambah via deposit                              |
| `is_banned`   | Default FALSE                                                 |

### User Commands

- `/start` — entry
- `/balance` — cek saldo
- `/history` — riwayat order paginated
- `/cancel ORDER_ID` — cancel pending order
- `/refund ORDER_ID ALASAN` — request refund
- `/voucher CODE` — cek voucher

### User Buttons (Reply Keyboard)

- 📋 List Produk
- 🎫 Voucher
- 📊 Laporan Stok
- 1, 2, 3, ... (angka produk)
- 💰 Deposit
- ❓ Cara Order
- ⚠️ Informasi (info user + saldo)

### Validasi User

- Auto-create on first interaction
- Banned user: `deduct_balance` & `add_balance` reject
- Balance check sebelum order saldo

---

## 12. Fungsi, Class, dan Modul Penting

### Domain Layer (`app/domain/`)

#### `entities.py`

- **`User`** — dataclass: telegram_id, username, balance, is_banned, dll
- **`Product`** — dataclass: id, name, description, short_description, category, price, stock, is_active
- **`Order`** — dataclass: id (UUID), user_id, product_id, variant_id, quantity, total_price, status, payment_method, payment_ref
  - Method `can_cancel()` — return True jika status="pending"
  - Method `mark_paid()` — set status="paid"
- **`Voucher`** — dataclass: id, code, discount_type, discount_value, min_purchase, max_discount, max_usage, used_count, is_active, expired_at
  - Method `is_valid()` — check is_active + not exhausted + not expired
  - Method `calculate_discount(total_price)` — return jumlah diskon

#### `interfaces.py` (ABC)

- **`ProductRepository`** — `list_paginated()`, `count()`, `get_by_id()`, `decrement_stock()` (legacy, tidak dipakai)
- **`UserRepository`** — `get_or_create()`, `get_by_id()`, `deduct_balance()`, `add_balance()`
- **`OrderRepository`** — `create()` (with variant_id), `get_by_id()`, `get_by_user()`, `update_status()`, `update_payment_ref()`
- **`PaymentGateway`** — `create_qris_deposit()`
- **`VoucherRepository`** — `get_by_code()`, `increment_usage()`, `has_user_used()`, `record_usage()`, `create()`, `list_active()`, `deactivate()`

### Application Layer (`app/application/services/`)

#### `factory.py`

- Singleton factory functions:
  - `get_order_service()`
  - `get_deposit_service()`
  - `get_payment_service()`
  - `get_voucher_service()`
- Lazy-load dependencies (repositories)

#### `order_service.py`

- **`OrderService.execute_order(user_id, product_id, quantity, payment_method, variant_id, unit_price)`**
  - Validate produk exists & available
  - Validate stock cukup
  - Hitung total (pakai unit_price kalau ada, fallback ke product.price)
  - Saldo: deduct balance atomic
  - Create order dengan variant_id
  - Return `OrderResult` (success/error)

#### `deposit_service.py`

- **`DepositService.create_deposit(user_id, amount)`** — generate QRIS via Tripay
- **`DepositService.process_deposit_callback(user_id, amount, payment_ref)`** — add balance setelah paid
- **`DepositService.get_user_balance(user_id)`** — helper
- Constants: `MIN_DEPOSIT = 10_000`, `MAX_DEPOSIT = 10_000_000`

#### `payment_service.py`

- **`PaymentService.process_order_payment(order_id, status, payment_ref)`** — update order status berdasarkan callback
- **`PaymentService.process_deposit_payment(...)`** — sama tapi untuk deposit
- **`PaymentService.verify_signature(payload, signature)`** — HMAC verify (legacy, sekarang verify-nya di TripayClient)
- Static `_map_gateway_status()` — Tripay status → internal status

#### `voucher_service.py`

- **`VoucherService.validate_voucher(code, user_id, total_price)`** — return `VoucherValidationResult` (valid + voucher + discount + error)
- **`VoucherService.apply_voucher(voucher_id, user_id, order_id)`** — increment + record usage
- **`VoucherService.create_voucher(...)`**, `list_active_vouchers()`, `deactivate_voucher()`

#### `delivery_service.py`

- **`deliver_accounts(order_id, product_id, quantity, user_id, variant_id)`**:
  - Get template (variant > product fallback)
  - Fetch N akun dari pool variant (FIFO + FOR UPDATE SKIP LOCKED)
  - Mark `is_used=TRUE`, set `used_by`, `order_id`, `used_at`
  - Sync stock variant + parent
  - Format pakai `_format_account()` (template-based)
  - Return `DeliveryResult(success, accounts, formatted_text, error)`

### Infrastructure Layer (`app/infrastructure/`)

#### `database/connection.py`

- `init_pool()`, `close_pool()`, `get_pool()`, `test_db_connection()`
- **Penting:** `statement_cache_size=0` di `create_pool()` — wajib untuk Supabase Pooler

#### `database/factory.py`

- Singleton repository factory dengan auto-fallback ke Mock kalau DB ga reachable

#### `database/product_repo.py`

- `AsyncPgProductRepository` — pakai dynamic stock query (sum dari account_stock count)
- `MockProductRepository` — fallback in-memory

#### `database/user_repo.py`, `order_repo.py`, `voucher_repo.py`

- Same pattern: AsyncPg + Mock

#### `payment/tripay.py`

- `TripayClient(api_key, private_key, merchant_code, sandbox)` — async HTTP via httpx
- `create_qris_deposit()`, `create_order_payment()`, `get_transaction_detail()`, `verify_callback_signature()`
- Singleton: `get_tripay_client()`

### Presentation Layer (`app/presentation/`)

#### `telegram/handlers/start.py`

- `cmd_start()`, `format_product_list()`, `_get_total_products()`, `_total_pages()`, `_get_products_page()`
- Handler: pagination, popular shortcut

#### `telegram/handlers/menu.py`

- Reply keyboard buttons handlers
- `handle_product_number()` — resolve sequential number → product → tampilkan variants atau direct order
- `handle_variant_selection()` — variant detail + qty selector
- Catch-all handler untuk unknown text

#### `telegram/handlers/order.py`

- `execute_order()` — main order handler (saldo & QRIS branches)
- `_notify_admin_new_order()` — kirim notif admin dengan delivered accounts
- `_generate_qr_image()` — generate QR PNG dari EMV QRIS string
- `_is_valid_qris_string()` — check apakah qr_string asli (>=50 chars + bukan "SANDBOX MODE")
- `_auto_expire_qris()` — background task

#### `telegram/handlers/admin.py` (~2700 lines)

- ~30 commands dengan FSM untuk yang interactive
- Helpers: `_is_admin()`, `_cancel_kb()`, `_field_kb()`, `_category_kb()`, `_confirm_kb()`
- Constants: `QRIS_METHODS`, `VALID_CATEGORIES`, `VALID_FIELDS`, `VARIANT_EDIT_FIELDS`

#### `telegram/handlers/info.py`

- `cmd_balance()`, `cmd_history()`, `cmd_cancel()`, `cmd_refund()`
- `_find_order_by_partial_id()` — support partial 8-char ID
- `handle_refund_reject()` — admin reject refund flow

#### `telegram/handlers/deposit.py`

- Deposit flow: preset/manual amount → konfirmasi → generate QRIS

#### `telegram/handlers/voucher.py`

- `/voucher CODE` — check voucher info

#### `telegram/keyboards/`

- `reply.py` — `get_main_menu_keyboard(total_products)` — auto-adjust angka button
- `inline.py` — `get_pagination_keyboard()`
- `order.py` — `get_product_detail_keyboard()`, `get_note_choice_keyboard()`, `get_confirmation_keyboard()`

#### `web/callbacks.py`

- FastAPI app
- `POST /webhook/tripay` — main webhook endpoint
- `GET /health` — health check
- `set_bot()` — inject bot instance untuk send notif
- `_handle_deposit_callback()`, `_handle_order_callback()`

### `main.py`

- `on_startup()`, `on_shutdown()` — lifecycle hooks
- `_register_commands(bot)` — set bot commands per scope (user vs admin)
- `run_bot()` — aiogram polling
- `run_webhook_server()` — uvicorn FastAPI
- `_cleanup_stale_orders()` — background task setiap 30 menit
- `main()` — gather 3 tasks paralel

---

## 13. Cara Menjalankan Project

### Prerequisites

- Python 3.10+ (project ditest pakai Python 3.14)
- Akses Supabase project (atau Postgres lain)
- Bot token Telegram dari @BotFather
- Tripay account (sandbox sudah cukup untuk dev)
- Optional: ngrok (untuk expose webhook ke public URL)

### Step 1: Setup Virtual Environment

```bash
cd c:\bot-auto-order
python -m venv .venv
.venv\Scripts\activate  # Windows
# atau
source .venv/bin/activate  # Linux/Mac
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Setup `.env`

Buat file `.env` di root project, isi sesuai template di section 4.

### Step 4: Setup Database

1. Login ke Supabase dashboard → SQL Editor
2. Jalankan migrations berurutan:
   - `migrations/001_init_schema.sql`
   - `migrations/002_vouchers.sql`
   - `migrations/003_account_stock.sql`
   - `migrations/004_account_template.sql`
   - `migrations/005_product_variants.sql`
3. (Optional) Seed initial products: `python seed_db.py`

### Step 5: Run Bot

```bash
python main.py
```

Bot akan jalan dengan output:

```
🌐 Mode: development - running bot + webhook server
INFO:     Uvicorn running on http://0.0.0.0:8080
✅ Admin commands registered for user 6405535980
✅ Bot commands registered (user: 6, admin: 33)
🚀 Bot siap! Kirim /start di Telegram.
✅ Database connection OK
```

### Step 6: Test

1. Buka Telegram → cari bot
2. `/start` → harusnya muncul list produk
3. Test flow user (browse, order saldo)

### Setup Webhook untuk Tripay (Optional, untuk test real callback)

```bash
# Terminal 2
ngrok http 8080

# Copy URL ngrok (https://xxx.ngrok-free.app)
# Set di Tripay Dashboard → Merchant → Callback URL
# Format: https://xxx.ngrok-free.app/webhook/tripay
```

### Test Webhook tanpa Ngrok

Pakai admin command `/testwebhook ORDER_ID` — simulasi callback PAID langsung.

### Production Deployment (Belum dilakukan)

- Belum ada deployment guide. Asumsi deploy ke VPS dengan:
  - systemd service untuk `python main.py`
  - nginx reverse proxy ke port 8080
  - SSL via Let's Encrypt
  - Set `ENVIRONMENT=production` di .env (akan trigger Tripay pakai production URL)

---

## 14. Testing dan Debugging

### Testing Manual

File `TESTING_CHECKLIST.md` di root project — 50+ test cases dikelompokkan A-O:

- A-E: Test sebagai user (start, navigasi, order saldo, QRIS, edge cases)
- F-O: Test sebagai admin (product CRUD, variant, stock, bulk, voucher, analytics, webhook, notif, cleanup)
- Bug regression check section

### Test Commands Bot

- `/testwebhook ORDER_ID` — simulate Tripay callback PAID
- `/webhookinfo` — lihat config webhook

### File Test Lama (legacy, mungkin outdated)

- `test_db.py` — test koneksi DB
- `test_integration.py` — test integration (perlu dicek ulang isinya)

### Error & Solusi yang Pernah Terjadi

#### 1. Supabase IPv6 only — connection refused

**Solusi:** Pakai Pooler URL (port 6543), bukan direct connection (port 5432).

#### 2. `DuplicatePreparedStatementError` di asyncpg

**Penyebab:** Supabase Pooler (PgBouncer) tidak support prepared statements.
**Solusi:** Set `statement_cache_size=0` di `create_pool()`.

#### 3. Tripay sandbox `qr_string` = "SANDBOX MODE"

**Penyebab:** Sandbox mode tidak return EMV QRIS asli.
**Solusi:** `_is_valid_qris_string()` check — jika "SANDBOX MODE", tampilkan text + checkout link saja (tanpa QR image). Production mode akan generate QR dari qr_string asli.

#### 4. Tripay minimum amount Rp 1.000

**Penyebab:** API constraint Tripay.
**Solusi:** Set semua harga produk testing minimal Rp 1.000.

#### 5. `TelegramNetworkError: Cannot connect to api.telegram.org`

**Penyebab:** Network unstable / ISP block.
**Solusi:** Bukan code bug. Pakai DNS bagus (Cloudflare 1.1.1.1) atau VPN jika ISP block.

#### 6. `aiogram 3.0.0` `AiohttpSession(connector=...)` TypeError

**Penyebab:** API berbeda di aiogram 3.0.
**Solusi:** Pakai default session (`Bot(token=BOT_TOKEN)` tanpa custom session).

#### 7. `NameError: product_id is not defined` di menu.py

**Penyebab:** Refactor ke `seq_number`, tapi `product_id` masih di-reference.
**Solusi:** Ganti ke `product.id`.

#### 8. Stok tidak berkurang setelah order

**Penyebab:** OrderService tidak pass variant_id ke order_repo.create. Akun di-fetch dari pool product-level (variant=NULL), bukan dari variant.
**Solusi:** Tambah `variant_id` parameter di execute_order, simpan di orders table, fetch akun dari variant pool. Bug fix ini sudah verified via integration test.

### Bug Yang Masih Ada (Saat Backup Dibuat)

⚠️ **Refund Reject Handler Konflik dengan Catch-All:**
File `info.py` punya `@router.message(F.text)` untuk `handle_refund_reject_reason()`. Filter ini bakal match SEMUA text message. Sebenarnya logic-nya udah filter via state check di awal handler, tapi ini bisa ngablok handler lain yang ada di router setelah info.py.

Saat ini urutan router di main.py: admin → **info** → start → voucher → deposit → order → menu (catch-all). Karena info ada di awal, handler `F.text` di info bisa "swallow" message yang harusnya untuk handler lain.

**Perlu cek ulang:** Pastikan filter state check di `handle_refund_reject_reason()` benar-benar return None (bukan answer message) jika bukan in state, supaya aiogram lanjut ke handler berikutnya.

⚠️ **Voucher belum integrate ke order checkout:**
Voucher backend ready, tapi user belum bisa apply voucher saat order. Cuma bisa cek info via `/voucher CODE`. Perlu ditambah step di order flow untuk input kode voucher → apply discount.

⚠️ **Refund approve belum auto:**
Admin tap "Tolak" sudah ada flow. Tapi admin "Approve" masih manual (kirim saldo via... belum ada command). Perlu tambah `/refund_approve ORDER_ID` yang auto-add balance + update status.

---

## 15. Keputusan Teknis yang Sudah Diambil

### 1. Aiogram 3.x bukan PTB / aiogram 2.x

- Async-first (lebih cocok untuk concurrent users)
- Modern filter API + FSM built-in
- Type hints lebih baik

### 2. asyncpg bukan supabase-py

- supabase-py v2 default sync (pakai PostgREST)
- asyncpg native + atomic UPDATE dengan `FOR UPDATE SKIP LOCKED`
- Lebih cepat untuk concurrency tinggi

### 3. Clean Architecture

- 4 layer: domain → application → infrastructure → presentation
- Dependency arrow ke dalam (presentation depends on application, dst)
- Memudahkan testing (mock repositories), maintenance, dan extension

### 4. Mock Repository Fallback

- Kalau DB ga reachable saat startup, auto-fallback ke in-memory mock
- Bot tetap bisa run untuk testing UI tanpa DB
- Tidak loss data karena init pool dicheck dulu

### 5. UUID untuk Order ID

- Bukan auto-increment integer
- Aman untuk distributed system
- Dipakai sebagai `merchant_ref` di Tripay (max 50 chars)

### 6. Polling bukan Webhook untuk Telegram

- Lebih simple untuk dev (no SSL, no domain)
- Performance cukup untuk <1000 user concurrent
- Switch ke webhook nanti kalau scale

### 7. FastAPI untuk Webhook Tripay (paralel dengan polling)

- Tripay butuh public URL untuk callback
- FastAPI ringan + async
- Run paralel dengan bot polling via `asyncio.gather()`

### 8. Variant System

- Initial design: single product per row
- Refactor: parent product (CANVA, NETFLIX) + variants (Canva 1 Bulan, Canva 1 Tahun)
- Variant punya price, stock (real-time dari account_stock count), template
- Migrasi: produk lama (id 13-21) di-deactivate, produk 1-21 jadi parent, variants di-create

### 9. Real-time Stock Calculation

- Awalnya: stock disimpan di kolom `products.stock` dan `product_variants.stock`
- Masalah: bisa de-sync dengan jumlah akun aktual di `account_stock`
- Solusi: query dynamic — `SELECT COUNT(*) FROM account_stock WHERE variant_id = X AND is_used = FALSE`
- Stock di kolom DB sekarang cuma cache, di-update saat `addstock`/`deliver`

### 10. Sequential Number di List Produk

- User lihat `[1], [2], [3]...` — sequential index sesuai abjad nama
- BUKAN product ID database (yang tetap fixed dan tidak berubah)
- Saat user tap nomor → bot resolve ke produk ke-N dari sorted list
- Alasan: ID database bisa skip (1, 5, 7, 11) kalau ada produk dihapus → tidak intuitive untuk user

### 11. Auto-Delivery via Account Stock Pool

- Admin tambah pool akun via `/addstock` (per variant)
- Saat order paid, bot ambil 1 akun dari pool, mark used, kirim ke user
- Format akun pakai template (`Email|Password|Profile|PIN`) — admin set via `/settemplate`
- Race-condition safe pakai `FOR UPDATE SKIP LOCKED`

### 12. Deskripsi 3-Tier

- `short_description` — overview di list (singkat, e.g. "Netflix Premium Shared")
- `description` — detail variant (singkat per variant, e.g. "1 Profile 1 User 1 Bulan")
- `delivery_description` — pesan setelah paid (panjang, T&C, syarat login)
- Logic: variant.delivery_description > product.delivery_description > skip

### 13. Hal yang Sengaja Dihindari

- ❌ ORM (SQLAlchemy) — pakai raw SQL via asyncpg untuk control penuh
- ❌ supabase-py REST API — kurang cocok untuk atomic ops
- ❌ Webhook mode Telegram — polling lebih simple untuk dev
- ❌ MongoDB — Postgres cukup, plus relasi (orders ↔ users, account_stock ↔ variants) butuh JOIN
- ❌ Float untuk uang — pakai BIGINT (IDR cents/rupiah tanpa desimal)

---

## 16. Progress Terakhir

### Fitur Selesai (✅)

- ✅ Clean Architecture project structure
- ✅ Database schema + 5 migrations (users, products, variants, orders, account_stock, vouchers, voucher_usages)
- ✅ Repository pattern (AsyncPg + Mock fallback)
- ✅ Bot UI (8 handlers: start, menu, order, deposit, admin, voucher, info)
- ✅ Reply keyboard auto-adjust
- ✅ FSM untuk order flow + admin interactive commands
- ✅ Tripay integration (sandbox + production-ready)
- ✅ QR generation (sandbox = text only, production = QR image dari EMV string)
- ✅ Webhook callback (signature verify, status update, notif)
- ✅ Auto-delivery akun via `account_stock` pool
- ✅ Variant system (parent product + variants)
- ✅ Real-time stock calculation (dynamic query)
- ✅ Deskripsi 3-tier
- ✅ Voucher system (backend ready)
- ✅ Admin commands ~33 commands (product/variant/stock/voucher CRUD, bulk ops, analytics)
- ✅ User commands (`/balance`, `/history`, `/cancel`, `/refund`)
- ✅ Refund flow with reason + admin reject
- ✅ Auto-cleanup stale pending orders (background task setiap 30 menit)
- ✅ Bot commands per scope (admin vs user)
- ✅ Excel export laporan
- ✅ Auto-delete flow messages setelah order saldo sukses
- ✅ Notifikasi admin include delivered accounts
- ✅ Laporan stok breakdown per variant

### File Terakhir yang Diedit

- `app/presentation/telegram/handlers/info.py` — refund flow + reject handler
- `app/presentation/telegram/handlers/admin.py` — bulk delete commands
- `app/presentation/telegram/handlers/order.py` — cleanup messages, notif admin dengan akun
- `app/presentation/telegram/handlers/menu.py` — laporan stok breakdown variant, real-time stock query
- `app/application/services/order_service.py` — variant_id + unit_price params
- `app/application/services/delivery_service.py` — variant-aware delivery
- `app/infrastructure/database/order_repo.py` — variant_id support
- `app/infrastructure/database/product_repo.py` — short_description, dynamic stock
- `main.py` — register bulkdel command, \_cleanup_stale_orders task
- `app/presentation/telegram/states.py` — RefundRejectStates
- `TESTING_CHECKLIST.md` — created

### Masalah Terakhir yang Sedang Dibahas

1. **Bug refund:** ID truncated 8-char dari `/history` tidak match exact ID di DB → fixed dengan `_find_order_by_partial_id()` (pakai LIKE prefix + filter user_id)
2. **Auto-delete flow messages:** Sudah selesai untuk saldo. QRIS belum di-implement (pesan QRIS pending masih ada setelah paid via webhook — tidak otomatis dihapus).
3. **Refund reject:** Sudah ada tombol "❌ Tolak" di notif admin, dengan flow input alasan via FSM. Belum ditambah flow approve refund.

### Next Step Paling Masuk Akal

1. **Fix bug refund reject handler** — pastikan `@router.message(F.text)` di info.py tidak konflik dengan handler lain
2. **Auto-delete QRIS pesan setelah paid via webhook** — sama seperti saldo cleanup
3. **Implement `/refund_approve ORDER_ID`** — admin auto-add balance ke user + update order status
4. **Integrate voucher ke order flow** — user input kode voucher saat checkout, discount apply otomatis
5. **Test end-to-end real payment via ngrok** — setelah merchant Tripay approved
6. **Production deployment guide** — VPS setup, systemd service, nginx, SSL

---

## 17. To-Do List Lanjutan

### 🔴 Prioritas Tinggi

#### 1. Fix konflik handler `F.text` di `info.py`

- **Apa:** `handle_refund_reject_reason()` di info.py pakai `@router.message(F.text)` yang bisa swallow message lain.
- **Kenapa penting:** Bisa bikin handler lain (catch-all di menu.py, FSM admin) tidak triggered.
- **File:** `app/presentation/telegram/handlers/info.py`
- **Risiko:** Kalau salah fix, refund reject ga jalan.
- **Solusi:** Pakai filter state (`F.text & StateFilter(RefundRejectStates.waiting_for_reason)`) langsung di decorator, bukan check di body.

#### 2. Auto-delete QRIS message setelah webhook paid

- **Apa:** Saat ini setelah QRIS paid via webhook callback, pesan QRIS pending tidak dihapus. Perlu sama seperti saldo flow yang auto-cleanup.
- **Kenapa penting:** UX clean (chat tidak penuh pesan lama).
- **File:** `app/presentation/web/callbacks.py`
- **Tantangan:** Webhook handler tidak punya akses ke `qris_msg_id`. Perlu simpan `message_id` di tabel orders saat QRIS di-generate, lalu retrieve saat webhook dipanggil.
- **Risiko:** Schema change (tambah kolom `qris_message_id` di orders), perlu migration.

#### 3. Implement `/refund_approve ORDER_ID`

- **Apa:** Command admin untuk approve refund — auto-add balance ke user + update status order ke "refunded".
- **Kenapa penting:** Saat ini admin manual kirim saldo, prone to error.
- **File:** `app/presentation/telegram/handlers/admin.py` + `info.py` (tambah tombol "✅ Approve" di notif refund)
- **Risiko:** Tambah status "refunded" di CHECK constraint orders kalau belum ada (perlu cek schema).

### 🟡 Prioritas Menengah

#### 4. Integrate voucher ke order checkout

- **Apa:** Saat user checkout (sebelum konfirmasi), tambah step input kode voucher (optional). Apply discount jika valid.
- **Kenapa penting:** Voucher backend siap tapi user belum bisa pakai.
- **File:** `app/presentation/telegram/handlers/order.py` (tambah state `waiting_for_voucher_or_skip`), `voucher_service.py` integration
- **Risiko:** Order flow jadi 1 step lebih panjang. Pastikan FSM state-nya benar.

#### 5. Cleanup pesan QRIS lebih advanced (multi-message tracking)

- **Apa:** Saat order via QRIS, tracking semua pesan flow (variant detail, catatan, konfirmasi, QRIS) → hapus semua setelah paid.
- **Sama seperti #2** tapi cakupannya lebih luas.

#### 6. Production migrate

- Set `ENVIRONMENT=production` di .env
- Update product prices ke harga asli (sekarang masih Rp 1.000 untuk testing)
- Setup VPS / cloud deploy
- SSL untuk webhook URL
- Update Tripay callback URL ke domain production

### ⚪ Prioritas Rendah

#### 7. /history detail per order

- Tap order di history → lihat detail lengkap + akun yang dikirim
- Berguna kalau user lupa akunnya

#### 8. Multi-admin support

- Sekarang admin = single ID di env. Tambah admin via command `/addadmin USER_ID`?
- Plus role-based: super-admin vs operator

#### 9. Analytics improvements

- Chart visualisasi (line chart penjualan harian)
- Export PDF laporan

#### 10. Cleanup unused dependencies

- Remove `python-telegram-bot`, `sqlalchemy`, `requests` dari requirements.txt
- Mereka tidak dipakai, cuma bikin install lebih lama

#### 11. Test framework setup

- pytest sudah di requirements tapi belum ada test files yang serius
- `test_db.py` dan `test_integration.py` perlu direview

---

## 18. Catatan untuk AI Agent Baru

### Aturan Wajib

1. ✅ **Baca `AI_RULES.md`** dulu sebelum mulai. File ini define Clean Architecture rules.
2. ✅ **Pertahankan struktur Clean Architecture** — domain → application → infrastructure → presentation. JANGAN gabungkan layer.
3. ✅ **Async-first** — JANGAN pakai `requests`, `psycopg2`, atau library blocking lain. Pakai `httpx`, `asyncpg`.
4. ✅ **Type hints** — semua function wajib ada type hints.
5. ✅ **Atomic queries** — operasi sensitif (stock decrement, balance deduct) WAJIB pakai single SQL UPDATE dengan guard. JANGAN load-then-update di Python.
6. ✅ **FSM untuk multi-step input** — JANGAN pakai global variable.
7. ✅ **Pagination** — semua list panjang wajib paginate (Telegram limit 4096 chars).
8. ✅ **Try-except wrap** — bungkus DB / API calls dengan try-except, log error, kasih pesan user-friendly.

### Hal yang JANGAN Dilakukan

1. ❌ JANGAN ubah goal utama project (digital product store auto-order bot).
2. ❌ JANGAN hapus fitur yang sudah ada tanpa konfirmasi user.
3. ❌ JANGAN re-init project dari nol — kode existing masih solid.
4. ❌ JANGAN tampilkan secret asli (BOT_TOKEN, TRIPAY keys) saat respond ke user. Kalau perlu reference, pakai placeholder.
5. ❌ JANGAN ganti Postgres → MongoDB / SQLite. Project sudah didesain untuk Postgres.
6. ❌ JANGAN ganti aiogram → PTB / library lain.
7. ❌ JANGAN add `python-telegram-bot` import — itu legacy, tidak dipakai.
8. ❌ JANGAN remove `statement_cache_size=0` di asyncpg — wajib untuk Supabase Pooler.
9. ❌ JANGAN hardcode admin ID — selalu pakai `ADMIN_IDS` env var.
10. ❌ JANGAN pakai float untuk uang — selalu BIGINT (IDR rupiah).

### Tips Workflow

- Saat user request fitur, baca `PROGRESS.md` dulu untuk lihat status terakhir.
- Saat ada bug, baca log terminal user dulu (biasanya user paste log) — debugging lebih akurat.
- Saat refactor, run syntax check: `python -c "import ast; ast.parse(open('FILE.py', encoding='utf-8').read())"`.
- Saat add command baru, update `_register_commands()` di main.py — admin popup.
- Saat add migration, buat file `migrations/00X_xxx.sql`, run via Supabase SQL editor.

### Style Coding

- Comments dalam bahasa Indonesia (mix dengan English untuk technical terms)
- Logger dipakai (`logger = logging.getLogger(__name__)`) di setiap module
- Indonesian text di response bot (sesuai target Indonesian users)
- Inline keyboard dengan emoji intuitive (✅, ❌, 🔙, ⏳, dll)
- Format response pakai monospace block kalau perlu align (`<code>` HTML tag), tapi user prefer text biasa untuk readability

### File Penting yang Sering Diedit

1. `app/presentation/telegram/handlers/admin.py` — paling besar, hati-hati saat edit (gunakan str_replace dengan context yang cukup unik)
2. `app/presentation/telegram/handlers/order.py` — flow order dengan banyak FSM
3. `app/presentation/telegram/handlers/menu.py` — variant flow + reply keyboard handlers
4. `app/application/services/order_service.py` & `delivery_service.py` — business logic core
5. `app/presentation/web/callbacks.py` — webhook handler

### Cara User Komunikasi

- User pakai bahasa Indonesia campur English ("gas implement", "tolong fix bug ini")
- User suka kasih screenshot untuk show issue
- User pakai log terminal untuk debug ("lu cek log di terminal 4")
- User paham tech (programmer), tapi prefer kalau AI proaktif analisa sebelum eksekusi
- User suka konfirmasi sebelum eksekusi major changes

---

## 19. Dokumentasi Command/Menu Bot

### USER Commands

| Command                   | Fungsi                                | Akses                 | File Handler | Output                                      |
| ------------------------- | ------------------------------------- | --------------------- | ------------ | ------------------------------------------- |
| `/start`                  | Mulai bot, lihat banner + list produk | All                   | start.py     | Banner image + list produk + reply keyboard |
| `/balance`                | Cek saldo                             | All                   | info.py      | Saldo dalam Rp                              |
| `/history`                | Riwayat order paginated               | All                   | info.py      | List order (5/page) + tombol Prev/Next      |
| `/cancel ORDER_ID`        | Cancel pending order                  | All                   | info.py      | Konfirmasi cancel atau error                |
| `/refund ORDER_ID ALASAN` | Request refund                        | All (paid order only) | info.py      | Konfirmasi request dikirim                  |
| `/voucher CODE`           | Cek info voucher                      | All                   | voucher.py   | Detail voucher (discount, kuota, status)    |

### Reply Keyboard Buttons (User)

| Button          | Fungsi                                 | Handler                           |
| --------------- | -------------------------------------- | --------------------------------- |
| 📋 List Produk  | Tampilkan list produk paginated        | menu.py `menu_list_produk()`      |
| 🎫 Voucher      | Petunjuk redeem voucher                | menu.py `menu_voucher()`          |
| 📊 Laporan Stok | Stock breakdown per variant            | menu.py `menu_laporan_stok()`     |
| 1, 2, 3, ...    | Pilih produk by sequential number      | menu.py `handle_product_number()` |
| 💰 Deposit      | Mulai flow deposit                     | menu.py `menu_deposit()`          |
| ❓ Cara Order   | Petunjuk cara order                    | menu.py `menu_cara_order()`       |
| ⚠️ Informasi    | Info user (ID, username, saldo, level) | menu.py `menu_informasi()`        |

### Inline Buttons (User)

| Callback Data                | Fungsi                | Handler                                       |
| ---------------------------- | --------------------- | --------------------------------------------- |
| `page:N`                     | Pagination produk     | start.py `handle_pagination()`                |
| `shortcut:popular`           | Top 5 produk by stock | start.py `handle_popular_shortcut()`          |
| `variant:ID`                 | Pilih variant         | menu.py `handle_variant_selection()`          |
| `qty:plus/minus:PID:Q`       | Adjust qty            | order.py `handle_qty_change()`                |
| `qty:noop`                   | Display only          | order.py                                      |
| `checkout:saldo/now:PID:QTY` | Pilih payment method  | order.py `handle_checkout_method()`           |
| `note:fill/skip`             | Pilih catatan         | order.py `ask_for_note_text()`, `skip_note()` |
| `order:confirm`              | Konfirmasi order      | order.py `execute_order()`                    |
| `order:cancel`               | Cancel order flow     | order.py `cancel_order()`                     |
| `qris:cancel:ORDER_ID`       | Cancel QRIS payment   | order.py `cancel_qris_payment()`              |
| `deposit:start`              | Mulai deposit flow    | deposit.py `start_deposit_flow()`             |
| `deposit:preset:AMOUNT`      | Pilih nominal preset  | deposit.py `handle_deposit_preset()`          |
| `deposit:confirm:AMOUNT`     | Konfirmasi deposit    | deposit.py `confirm_deposit()`                |
| `deposit:cancel`             | Cancel deposit        | deposit.py `cancel_deposit()`                 |
| `history:page:N`             | Pagination history    | info.py `handle_history_page()`               |

### ADMIN Commands (33 total)

| Command                     | Fungsi                          | File     |
| --------------------------- | ------------------------------- | -------- |
| `/admin`                    | Menu admin (list semua command) | admin.py |
| `/stats`                    | Statistik bot                   | admin.py |
| **Payment**                 |                                 |          |
| `/setqris`                  | Ganti QRIS method (4 pilihan)   | admin.py |
| `/getqris`                  | Lihat QRIS method aktif         | admin.py |
| **Webhook**                 |                                 |          |
| `/testwebhook ORDER_ID`     | Simulasi callback PAID          | admin.py |
| `/webhookinfo`              | Info webhook setup ngrok        | admin.py |
| **Product**                 |                                 |          |
| `/listproduct`              | List semua produk + ID          | admin.py |
| `/addproduct`               | Add produk interactive 5-step   | admin.py |
| `/editproduct`              | Edit produk interactive         | admin.py |
| `/delproduct`               | Soft delete produk              | admin.py |
| `/restock ID QTY`           | Quick add/remove stock          | admin.py |
| `/bulkadd`                  | Add banyak produk paste         | admin.py |
| **Variant**                 |                                 |          |
| `/addvariant ID`            | Add variant interactive 4-step  | admin.py |
| `/editvariant ID`           | Edit variant interactive        | admin.py |
| `/delvariant ID`            | Soft delete variant             | admin.py |
| `/listvariant ID`           | List variants per produk        | admin.py |
| **Account Stock**           |                                 |          |
| `/addstock ID`              | Add akun ke variant interactive | admin.py |
| `/viewstock ID`             | Lihat stok akun                 | admin.py |
| `/stockall`                 | Summary stok semua produk       | admin.py |
| `/settemplate ID Tmpl`      | Set format template akun        | admin.py |
| **Bulk Operations**         |                                 |          |
| `/bulkdel product 1,2,3`    | Bulk delete produk              | admin.py |
| `/bulkdel variant 1,2,3`    | Bulk delete variant             | admin.py |
| `/bulkdel stock ID`         | Hapus akun unused di produk     | admin.py |
| `/bulkdel stockvar ID`      | Hapus akun unused di variant    | admin.py |
| **Voucher**                 |                                 |          |
| `/addvoucher CODE TYPE VAL` | Buat voucher                    | admin.py |
| `/listvoucher`              | List voucher aktif              | admin.py |
| `/delvoucher ID`            | Deactivate voucher              | admin.py |
| **User Management**         |                                 |          |
| `/banuser USER_ID`          | Ban user                        | admin.py |
| `/unbanuser USER_ID`        | Unban user                      | admin.py |
| `/broadcast PESAN`          | Kirim pesan ke semua user       | admin.py |
| **Analytics**               |                                 |          |
| `/report [period]`          | Laporan + tombol Detail/Excel   | admin.py |
| `/topproducts [N]`          | Produk terlaris                 | admin.py |
| `/topusers [N]`             | Top spender                     | admin.py |

### Admin Inline Buttons / Callbacks

| Callback Data                    | Fungsi                          |
| -------------------------------- | ------------------------------- |
| `admin:setqris:METHOD`           | Set QRIS method                 |
| `admin:cancel`                   | Cancel admin flow (any FSM)     |
| `admin:cat:CATEGORY`             | Pilih kategori produk           |
| `admin:field:FIELD`              | Pilih field edit                |
| `admin:addproduct:confirm`       | Konfirmasi add product          |
| `admin:addvariant:confirm`       | Konfirmasi add variant          |
| `admin:bulkadd:confirm`          | Konfirmasi bulk add             |
| `admin:delproduct:confirm`       | Konfirmasi delete product       |
| `admin:delvariant:confirm`       | Konfirmasi delete variant       |
| `editproduct:back:ID`            | Back ke field selection produk  |
| `editproduct:back_to_id`         | Back ke input ID produk         |
| `editvariant:select:VID`         | Pilih variant untuk edit        |
| `editvariant:field:FIELD`        | Pilih field variant             |
| `editvariant:back:VID`           | Back ke field selection variant |
| `editvariant:back_to_select:PID` | Back ke list variant            |
| `delvariant:select:VID`          | Pilih variant untuk delete      |
| `addstock:var:VID`               | Pilih variant untuk addstock    |
| `addstock:back:PID`              | Back ke list variant addstock   |
| `report:detail:PERIOD`           | Show detail transaksi           |
| `report:excel:PERIOD`            | Generate Excel report           |
| `refund:reject:OID:UID`          | Tolak refund (admin)            |
| `history:page:N`                 | Pagination history user         |

### FSM States (full list)

Lokasi: `app/presentation/telegram/states.py`

| State Group          | States                                                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `OrderStates`        | waiting_for_qty_or_checkout, waiting_for_note_choice, waiting_for_note_text, waiting_for_confirmation                           |
| `DepositStates`      | waiting_for_amount, waiting_for_confirmation                                                                                    |
| `AddProductStates`   | waiting_for_name, waiting_for_description, waiting_for_category, waiting_for_price, waiting_for_stock, waiting_for_confirmation |
| `EditProductStates`  | waiting_for_id, waiting_for_field, waiting_for_value                                                                            |
| `DelProductStates`   | waiting_for_id, waiting_for_confirmation                                                                                        |
| `BulkAddStates`      | waiting_for_data, waiting_for_confirmation                                                                                      |
| `AddVariantStates`   | waiting_for_name, waiting_for_code, waiting_for_description, waiting_for_price, waiting_for_confirmation                        |
| `AddStockStates`     | waiting_for_variant_select, waiting_for_accounts                                                                                |
| `EditVariantStates`  | waiting_for_variant_select, waiting_for_field, waiting_for_value                                                                |
| `DelVariantStates`   | waiting_for_variant_select, waiting_for_confirmation                                                                            |
| `RefundRejectStates` | waiting_for_reason                                                                                                              |

---

## 20. Quick Reference: Setup dari Nol

```bash
# 1. Clone / extract project
cd c:\bot-auto-order

# 2. Virtual env
python -m venv .venv
.venv\Scripts\activate

# 3. Install deps
pip install -r requirements.txt

# 4. Setup .env (copy template di section 4, isi credentials)

# 5. Run migrations di Supabase SQL Editor (urut 001 → 005)

# 6. (Optional) Seed produk
python seed_db.py

# 7. Run bot
python main.py

# 8. (Optional) Expose webhook untuk test Tripay real
ngrok http 8080
# Copy URL → Tripay Dashboard → Callback URL: https://xxx.ngrok-free.app/webhook/tripay
```

---

## 📌 Catatan Akhir untuk AI Agent Baru

Project ini sudah dalam kondisi **functional** untuk:

- Test sebagai user via saldo (full flow: order → paid → akun terkirim)
- Test sebagai admin (manage produk, variant, stock, voucher, dll)
- Test webhook callback via `/testwebhook` (tanpa ngrok)

Project **belum tested** untuk:

- Real payment via QRIS production (merchant Tripay masih "Dalam Review")
- Concurrent users dalam jumlah besar
- Production deployment

Yang **sangat penting** untuk AI agent baru:

1. **Baca `AI_RULES.md`** sebelum coding
2. **Baca `PROGRESS.md`** untuk status terkini
3. **Baca section 14, 16, 17** di file ini untuk konteks bug & next step
4. **Jangan refactor major** tanpa konfirmasi user
5. **User suka step-by-step explanation** sebelum eksekusi

Kalau ada yang tidak jelas dari dokumentasi ini, silakan baca file aslinya — semua source code lengkap di repo.

Good luck! 🚀

---

_End of PROJECT_CONTEXT_BACKUP.md_
