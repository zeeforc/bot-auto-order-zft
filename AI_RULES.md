# 🤖 Kiro AI System Instructions untuk T-Store Auto Order Bot

## 1. Project Context
Ini adalah project bot Telegram untuk otomatisasi penjualan produk digital (akun, lisensi, dll) yang beroperasi 24/7.
- **Bahasa:** Python 3.10+
- **Framework:** Aiogram 3.x (Wajib Async)
- **Database:** Supabase (PostgreSQL) via async driver
- **Payment Gateway:** Tripay (QRIS & VA)

## 2. Architecture Rules (STRICT!)
Project ini **WAJIB** mematuhi Clean Architecture. JANGAN PERNAH merusak struktur ini atau menggabungkan layer yang berbeda:
- `app/domain/`: Hanya berisi abstraksi (Interfaces/ABC), entities, dan core business logic. Dilarang ada kode library eksternal (seperti aiogram atau koneksi db langsung) di sini.
- `app/infrastructure/`: Hanya berisi implementasi Database (ProductRepo, UserRepo) dan API eksternal (TripayClient).
- `app/presentation/telegram/`: Hanya berisi Telegram Handlers, Keyboards, dan FSM States.
- `config/`: Hanya untuk load environment variable dari `.env`.

## 3. Coding Guidelines (Wajib Dipatuhi AI)
- **Asynchronous First:** JANGAN PERNAH menggunakan library *blocking* / *synchronous* seperti `requests` atau `psycopg2`. Gunakan `aiohttp`, `asyncpg`, atau client async lainnya.
- **Type Hinting:** Semua fungsi dan method WAJIB memiliki *Type Hints* yang jelas (misal: `async def get_user(id: int) -> dict:`).
- **FSM untuk State:** Semua input user yang berupa alur (seperti milih qty, ngisi catatan, checkout) WAJIB menggunakan `aiogram.fsm`. JANGAN gunakan global variable.
- **Pagination:** Semua list yang panjang (produk, histori) wajib di-slice/paginate agar tidak melebihi limit 4096 karakter Telegram.
- **Error Handling:** Bungkus proses pemanggilan API (database/payment) dengan `try-except` dan berikan pesan error yang *user-friendly* ke user, log error aslinya di backend.

## 4. Race Condition & Concurrency
- Saat memotong stok produk atau saldo user, WAJIB gunakan *Atomic Query* / *Optimistic Locking* di level database (contoh: `UPDATE products SET stock = stock - qty WHERE id = X AND stock >= qty`). JANGAN kurangi stok di level memori Python.

## 5. AI Communication Protocol
Jika saya (User) meminta lu (Kiro AI) untuk membuat fitur baru:
1. Baca file ini terlebih dahulu untuk memahami arsitektur.
2. Tentukan fitur ini akan ditaruh di layer mana (Domain, Infrastructure, atau Presentation).
3. Jangan mengubah kode yang sudah berjalan kecuali diminta.
4. Berikan *output* kode lengkap beserta letak/path file-nya.

## Biasakan setiap kali ada command baru, langsung tambahkan ke popup command