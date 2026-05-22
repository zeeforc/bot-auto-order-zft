# 🧪 Webhook Testing Guide

Semua produk sudah di-set harga Rp 1 untuk memudahkan testing payment.

## Quick Start

### 1. Jalankan Bot + Webhook Server

```bash
python main.py
```

Output akan terlihat seperti:

```
🌐 Mode: development - running bot + webhook server
🚀 Bot siap! Kirim /start di Telegram.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

Bot polling + webhook server jalan bersamaan.

---

## Testing Options

### Option A: Test Manual (Tanpa Ngrok)

**Paling cepat untuk quick test!**

1. Buat order via bot:
   - Kirim `/start` → pilih produk → "Buy Now" (QRIS)
   - Copy ORDER_ID dari pesan

2. Simulasi callback:

   ```
   /testwebhook ORDER_ID
   ```

3. Cek notifikasi:
   - User dapat: "✅ PEMBAYARAN BERHASIL"
   - Admin dapat: "🔔 ORDER BARU - SUDAH DIBAYAR!"

**Keuntungan:** Cepat, tidak perlu setup ngrok
**Kekurangan:** Tidak test real Tripay callback

---

### Option B: Test dengan Ngrok (Real Tripay Callback)

**Untuk test real payment flow!**

#### Step 1: Install Ngrok

Download dari: https://ngrok.com/download

Atau pakai Chocolatey (Windows):

```powershell
choco install ngrok
```

#### Step 2: Jalankan Bot

```bash
python main.py
```

#### Step 3: Buka Terminal Baru & Jalankan Ngrok

```bash
ngrok http 8080
```

Output akan terlihat seperti:

```
Session Status                online
Account                       your-email@gmail.com
Version                       3.x.x
Region                        us (United States)
Latency                       45ms
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok-free.app -> http://localhost:8080
```

**Copy URL:** `https://abc123.ngrok-free.app`

#### Step 4: Set Callback URL di Tripay Dashboard

1. Buka: https://tripay.co.id/merchant/dashboard
2. Masuk ke Merchant Settings
3. Cari "Callback URL" atau "Webhook URL"
4. Paste: `https://abc123.ngrok-free.app/webhook/tripay`
5. Save

#### Step 5: Test Payment

1. Buat order via bot:
   - Kirim `/start` → pilih produk → "Buy Now" (QRIS)
   - Scan QRIS dengan e-wallet (GCash, Dana, OVO, dll)
   - Bayar Rp 1

2. Tunggu callback dari Tripay (biasanya instant)

3. Cek notifikasi:
   - User dapat: "✅ PEMBAYARAN BERHASIL"
   - Admin dapat: "🔔 ORDER BARU - SUDAH DIBAYAR!"

**Keuntungan:** Test real payment flow, real Tripay callback
**Kekurangan:** Perlu setup ngrok, perlu e-wallet dengan saldo

---

## Admin Commands untuk Testing

### `/testwebhook ORDER_ID`

Simulasi callback PAID tanpa perlu Tripay.

```
/testwebhook 550e8400-e29b-41d4-a716-446655440000
```

### `/webhookinfo`

Lihat info webhook setup.

```
/webhookinfo
```

Output:

```
🌐 WEBHOOK INFO

• Port: 8080
• Secret: DEV-***...***
• Endpoint: POST /webhook/tripay
• Health: GET /health

Setup ngrok:
ngrok http 8080

Tripay Callback URL:
https://YOUR-NGROK-URL/webhook/tripay
```

### `/stats`

Lihat statistik bot.

```
/stats
```

---

## Troubleshooting

### ❌ "Gagal membuat pembayaran"

**Kemungkinan:**

- Tripay credentials belum di-set di `.env`
- Network error ke Tripay API

**Solusi:**

1. Cek `.env`:
   ```
   TRIPAY_API_KEY=DEV-...
   TRIPAY_API_SECRET=...
   TRIPAY_MERCHANT_CODE=...
   ```
2. Cek koneksi internet
3. Cek Tripay API status: https://tripay.co.id

### ❌ "Webhook tidak terima callback"

**Kemungkingan:**

- Ngrok URL belum di-set di Tripay Dashboard
- Ngrok session expired (URL berubah)
- Firewall blocking

**Solusi:**

1. Cek Tripay Dashboard → Callback URL sudah benar?
2. Jalankan ngrok ulang (URL baru)
3. Update Tripay Dashboard dengan URL baru
4. Cek firewall/antivirus

### ❌ "Signature verification failed"

**Kemungkinan:**

- WEBHOOK_SECRET di `.env` salah
- Tripay private key tidak match

**Solusi:**

1. Cek `.env`:
   ```
   WEBHOOK_SECRET=8LhX9-owklV-76GEB-YtVWM-1i0Hk
   ```
   (Harus sama dengan TRIPAY_API_SECRET)
2. Cek Tripay Dashboard → Private Key

---

## Logs & Debugging

### Bot Logs

Lihat di terminal saat bot jalan:

```
[webhook] 📥 Incoming callback, signature present: True
[webhook] ✅ Signature verified
[webhook] 📋 Callback data: merchant_ref=... status=PAID amount=1
[webhook] ✅ Order payment notification sent to user 123456789
```

### Ngrok Logs

Buka: http://127.0.0.1:4040

Lihat semua request yang masuk ke webhook.

### Database Check

Cek order status di DB:

```sql
SELECT id, user_id, status, payment_ref FROM orders ORDER BY created_at DESC LIMIT 5;
```

---

## Next Steps

Setelah webhook testing berhasil:

1. **Priority 2: User Features**
   - `/history` - Lihat riwayat order
   - `/balance` - Check saldo
   - `/cancel ORDER_ID` - Cancel pending order

2. **Priority 3: Admin Features**
   - `/addproduct` - Add produk baru
   - `/editproduct` - Edit produk
   - `/delproduct` - Delete produk

3. **Priority 4: Analytics**
   - `/report` - Laporan penjualan
   - `/topproducts` - Produk terlaris

---

## Questions?

Cek logs di terminal atau hubungi support Tripay.

Good luck! 🚀
