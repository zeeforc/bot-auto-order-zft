# TARGET UPDATE: Integrasi Pembayaran GoPay QRIS Dinamis & Webhook MacroDroid

Gua ingin mengimplementasikan sistem pembayaran GoPay QRIS custom (tanpa potongan) dan webhook MacroDroid ke dalam project ini. Karena project ini menggunakan Clean Architecture (4 Layer), lu harus mematuhi aturan layer, async-first (aiogram 3.x + asyncpg), dan prinsip SOLID.

Berikut adalah spesifikasi teknis dan instruksi pembagian tugasnya per layer:

## 1. LAYER INFRASTRUCTURE (QRIS Generator)
- **Tugas:** Buat client/adapter baru untuk GoPay di `app/infrastructure/payment_clients/` (misal: `gopay_client.py`).
- **Implementasi:** 
  - Gunakan script manipulasi string EMVCo dan kalkulasi CRC16 (`crcmod.predefined.Crc('crc-ccitt-false')`).
  - Buat fungsi *async* `generate_dynamic_qris(amount: int) -> bytes` yang me-return bytes gambar QR Code.
  - Jika memungkinkan, *inherit* class ini dari Interface pembayaran yang sudah ada di layer Domain (seperti Tripay/Pakasir).

## 2. LAYER DOMAIN & APPLICATION (Business Logic)
- **Modifikasi Order Creation:** Saat user checkout menggunakan metode "GoPay Macro", tambahkan kode unik (misal: random 1-999 perak) ke `base_price` agar nominalnya unik untuk mendeteksi pembayaran. Pastikan logic ini ditaruh di `PaymentService` atau `OrderService`.
- **Atomic Operations:** Gunakan koneksi `asyncpg` yang atomic saat menyimpan pending order (dengan nominal final) ke tabel `orders`.
- **Modifikasi Webhook Service:** Pastikan ada *method* di `OrderService` (misal: `process_webhook_payment(amount: int)`) yang akan dipanggil oleh FastAPI. Method ini harus:
  1. Melakukan SELECT order dengan `amount` tersebut & status `PENDING`.
  2. Melakukan UPDATE status order menjadi `PAID`.
  3. Memanggil `DeliveryService` untuk mendistribusikan akun/produk.
  4. Mengirim notifikasi sukses ke user dan admin.
  *Note: Seluruh proses DB ini harus berjalan secara atomic (transactional).*

## 3. LAYER PRESENTATION (Bot Handlers & FastAPI Webhooks)
- **Telegram Bot (`app/presentation/handlers/`):** 
  - Di dalam flow checkout (kemungkinan berbasis FSM), tambahkan opsi pembayaran "GoPay QRIS (No Fee)".
  - Saat user memilih ini, bot akan memanggil `gopay_client` untuk mem-generate gambar QR, lalu mengirimkannya menggunakan `message.answer_photo` (atau `edit_message_media`) dengan *caption* berisi nominal unik yang HARUS dibayar.
- **FastAPI Webhook (`app/presentation/webhooks/` atau sejenisnya):**
  - Buat *endpoint* rahasia baru: `POST /webhook/gopay/secret_abc123`.
  - *Payload* dari MacroDroid berbentuk JSON: `{"pesan": "Teks notif gopay"}`.
  - Ekstrak nominal (*amount*) menggunakan regex (misal: `Rp\s?(\d+(?:\.\d+)*)`).
  - Panggil `OrderService.process_webhook_payment(amount)` untuk mengeksekusi *business logic*.

## ⚠️ STRICT RULES UNTUK EKSEKUSI INI:
1. **Dilarang keras** menggunakan `sqlite3` atau eksekusi I/O *blocking*. Selalu gunakan `async/await` (asyncpg, aiohttp).
2. **Jangan** mencampur *business logic* di dalam *handler* Telegram atau FastAPI. Handler hanya boleh menerima *request* dan memanggil layer Application (`Service`).
3. Pastikan pengetikan (*type hints*) kuat.
4. **Sebelum menulis kode**, berikan gua ringkasan (List) file mana saja yang akan lu:
   - [NEW] Bikin baru.
   - [MODIFY] Edit/Modifikasi.
   Gua harus *approve* list tersebut sebelum lu mulai menulis baris kode pertama.