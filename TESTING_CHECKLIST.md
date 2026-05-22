# 🧪 Testing Checklist - T-Store Auto Order Bot

## Persiapan

- [ ] Bot running (`python main.py`)
- [ ] Log terminal terbuka (monitor errors)
- [ ] Punya 2 akun Telegram (1 admin, 1 user biasa)

---

## 👤 TEST SEBAGAI USER BIASA

### A. Start & Navigasi

- [ ] Kirim `/start` → muncul banner + list produk + keyboard
- [ ] Keyboard layout rapi: [List Produk][Voucher][Laporan Stok] + angka + [Deposit][Cara Order][Informasi]
- [ ] Tekan back HP → keyboard hide
- [ ] Tap icon keyboard → keyboard muncul lagi
- [ ] Tap "📋 List Produk" → list produk muncul (sorted abjad, nomor sequential)
- [ ] Tap "📊 Laporan Stok" → breakdown per variant muncul
- [ ] Tap "❓ Cara Order" → instruksi muncul
- [ ] Tap "⚠️ Informasi" → info saldo + user muncul
- [ ] Tap "🎫 Voucher" → instruksi redeem muncul

### B. Order Flow (Saldo)

- [ ] Tap nomor produk → detail produk + list variant muncul
- [ ] Tap variant → detail variant + qty selector muncul
- [ ] Tap +/- → qty berubah, harga update
- [ ] Tap "Buy (Saldo)" → pilih catatan (skip/isi)
- [ ] Konfirmasi → order sukses
- [ ] Pesan 1: Detail transaksi + account data muncul
- [ ] Pesan 2: Delivery description (T&C) muncul (jika di-set)
- [ ] Stok variant berkurang setelah order
- [ ] Saldo berkurang sesuai total

### C. Order Flow (QRIS)

- [ ] Tap "Buy (Now)" → catatan → konfirmasi
- [ ] QRIS info muncul (sandbox: text + link, production: QR image)
- [ ] Tombol "❌ Batalkan Pembayaran" muncul
- [ ] Tap batal → order cancelled, pesan dihapus
- [ ] Tunggu 15 menit → auto-expire (pesan hilang, order cancelled)

### D. User Commands

- [ ] `/balance` → saldo muncul
- [ ] `/history` → riwayat order muncul (paginated)
- [ ] Tap Next/Prev → pagination works
- [ ] `/cancel ORDER_ID` → order pending di-cancel
- [ ] `/cancel ORDER_ID` (bukan milik) → ditolak
- [ ] `/refund ORDER_ID` → request dikirim ke admin
- [ ] `/voucher KODE` → voucher applied (jika valid)

### E. Edge Cases

- [ ] Order produk stok 0 → ditolak
- [ ] Order saldo kurang → ditolak
- [ ] Double-click konfirmasi → hanya 1 order
- [ ] Ketik angka invalid (misal 999) → error message
- [ ] Ketik text random → catch-all response

---

## 🔧 TEST SEBAGAI ADMIN

### F. Product Management

- [ ] `/listproduct` → list semua produk + ID
- [ ] `/addproduct` → interactive flow (5 step) → produk tersimpan
- [ ] `/editproduct` → pilih ID → pilih field → input value → saved
- [ ] Tombol "🔙 Kembali ke Produk" → balik ke field selection
- [ ] `/delproduct` → pilih ID → konfirmasi → produk nonaktif

### G. Variant Management

- [ ] `/addvariant ID` → interactive flow (4 step) → variant tersimpan
- [ ] `/listvariant ID` → list variant + ID + stok
- [ ] `/editvariant ID` → pilih variant → pilih field → input → saved
- [ ] Tombol "🔙 Kembali" → balik ke variant list
- [ ] `/delvariant ID` → pilih variant → konfirmasi → variant nonaktif

### H. Account Stock

- [ ] `/addstock ID` → pilih variant → paste akun → stok bertambah
- [ ] Format hint dinamis sesuai template
- [ ] Tombol "🔙 Kembali ke Variant" → bisa add ke variant lain
- [ ] `/viewstock ID` → lihat stok akun per produk
- [ ] `/stockall` → summary semua produk
- [ ] `/settemplate ID Label1|Label2|...` → template tersimpan

### I. Bulk Operations

- [ ] `/bulkadd` → paste multi-line → preview → konfirmasi → inserted
- [ ] `/bulkdel product 13,15,16` → produk dihapus
- [ ] `/bulkdel variant 1,2,3` → variant dihapus
- [ ] `/bulkdel stock 5` → semua akun unused di produk 5 dihapus
- [ ] `/bulkdel stockvar 3` → semua akun unused di variant 3 dihapus

### J. Voucher

- [ ] `/addvoucher CODE percent 10 100` → voucher created
- [ ] `/listvoucher` → list muncul
- [ ] `/delvoucher ID` → voucher deactivated

### K. User Management

- [ ] `/banuser USER_ID` → user banned
- [ ] `/unbanuser USER_ID` → user unbanned
- [ ] `/broadcast PESAN` → pesan terkirim ke semua user

### L. Analytics & Report

- [ ] `/report` → laporan hari ini muncul
- [ ] `/report weekly` → laporan 7 hari
- [ ] Tap "📋 Detail Transaksi" → list transaksi muncul
- [ ] Tap "📥 Download Excel" → file .xlsx terkirim
- [ ] `/topproducts` → ranking produk muncul
- [ ] `/topusers` → ranking user muncul

### M. Webhook & Payment

- [ ] `/webhookinfo` → info webhook muncul
- [ ] `/testwebhook ORDER_ID` → simulasi callback → notif ke user + admin
- [ ] `/setqris` → pilih method → updated
- [ ] `/getqris` → method aktif muncul

### N. Notifications

- [ ] Order paid (saldo) → admin dapat notif + data akun
- [ ] Order paid (QRIS via testwebhook) → admin dapat notif
- [ ] Refund request → admin dapat notif

### O. Auto-Cleanup

- [ ] Buat order QRIS, jangan bayar
- [ ] Tunggu 30+ menit → order auto-cancelled di DB

---

## 🐛 Bug Regression Check

- [ ] Stok berkurang setelah order (variant level)
- [ ] Stok parent = sum variant stocks
- [ ] Nomor di list produk sequential (1,2,3...) bukan ID
- [ ] Deskripsi di detail produk = short_description (bukan delivery_description)
- [ ] Delivery description hanya muncul di pesan setelah paid
- [ ] Template akun format sesuai (Email: xxx, Password: xxx, dll)
- [ ] Keyboard auto-adjust sesuai jumlah produk

---

## ✅ Sign-Off

| Tester | Tanggal | Status |
| ------ | ------- | ------ |
| Admin  |         | ⬜     |
| User   |         | ⬜     |

---

## Notes

Tulis bug/issue yang ditemukan di sini:

1.
2.
3.
