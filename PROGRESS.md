# 📊 T-Store Auto Order Bot - Progress & TODO

## ✅ Phase 1: Project Setup (DONE)

- [x] Clean Architecture structure
- [x] Aiogram 3.x async-first
- [x] Environment configuration (.env, settings.py)

## ✅ Phase 2: Database Integration (DONE)

- [x] Domain layer: Entities + Interfaces (ABC)
- [x] AsyncPg repositories (Product, User, Order, Voucher) + Mock fallback
- [x] Database schema + migrations
- [x] Atomic operations (UPDATE ... WHERE balance >= amount)
- [x] Supabase Pooler URL (IPv4 fix)

## ✅ Phase 2.5: Telegram Bot UI (DONE)

- [x] Handlers: start, menu, order, deposit, admin, voucher, info
- [x] Keyboards: reply (main menu), inline (pagination), order (detail/confirm)
- [x] FSM States: OrderStates + DepositStates
- [x] Logging + error handling + fallback

## ✅ Phase 3: Business Logic & Payment (DONE)

- [x] Service Layer: OrderService, DepositService, PaymentService, VoucherService
- [x] Order execution via saldo (atomic: deduct balance + stock + create order + rollback)
- [x] Deposit flow (FSM: preset/manual amount → confirm → generate QRIS)
- [x] Tripay QRIS generation (sandbox=text+link, production=QR EMV asli)
- [x] Admin panel: /admin, /setqris, /getqris, /stats
- [x] FastAPI webhook handler (POST /webhook/tripay)
- [x] main.py: bot polling + webhook server concurrent

## ✅ Phase 3.5: Voucher System (DONE)

- [x] Voucher table + VoucherRepository (AsyncPg + Mock)
- [x] VoucherService: validate, apply, track usage
- [x] Admin commands: /addvoucher, /listvoucher, /delvoucher
- [x] User command: /voucher CODE

## ✅ Phase 3.6: Order Payment via QRIS (DONE)

- [x] Generate QRIS real via Tripay
- [x] Sandbox: text + checkout link | Production: QR image EMV asli
- [x] Store payment reference di order
- [x] Double-click protection (anti-duplicate order)
- [x] Cancel button + Auto-expire 15 menit
- [x] Clean message deletion

## ✅ Phase 4: Webhook & Callbacks (DONE)

- [x] Webhook handler (POST /webhook/tripay) + signature verification
- [x] Auto-update order status (PAID → paid)
- [x] User notification (pembayaran berhasil)
- [x] Admin notification (order baru dibayar)
- [x] Deposit callback (auto add balance)
- [x] /testwebhook + /webhookinfo commands

## ✅ Phase 5: User Features (DONE)

- [x] /balance - Check saldo
- [x] /history - Riwayat order (paginated, 5/page, prev/next)
- [x] /cancel ORDER_ID - Cancel pending order (ownership check)
- [x] /refund ORDER_ID - Request refund (notify admin)

## ✅ Phase 6: Admin Features Extended (DONE)

- [x] /addproduct - Tambah produk (interactive FSM, step-by-step)
- [x] /editproduct - Edit produk (interactive: pilih ID → field → value)
- [x] /delproduct - Hapus produk (interactive + confirmation)
- [x] /restock ID QTY - Quick add stock (paling sering dipakai)
- [x] /listproduct - List semua produk dengan ID
- [x] /bulkadd - Add banyak produk sekaligus (paste multi-line)
- [x] /banuser USER_ID - Ban user
- [x] /unbanuser USER_ID - Unban user
- [x] /broadcast PESAN - Kirim pesan ke semua user

---

## 📝 TODO - Fitur Belum Selesai

### ⚪ Priority 4: Analytics & Reporting (DONE)

- [x] /report [daily|weekly|monthly] - Laporan penjualan
- [x] /topproducts [limit] - Produk terlaris
- [x] /topusers [limit] - User top spender

### ⚪ Priority 5: Production Deployment

- [ ] Switch ke Tripay production API (setelah merchant approved)
- [ ] Setup ngrok / VPS untuk webhook
- [ ] Set harga produk asli (bukan Rp 1.000 testing)
- [ ] Remove testing docs

---

## 🎯 Recommended Next Step

**Priority 5: Production Deployment** ← NEXT

Setelah merchant Tripay approved:

1. Ganti API key ke production
2. Set harga produk asli
3. Setup VPS/ngrok untuk webhook
4. Go live! 🚀

---

## 📊 Current Stats

| Komponen       | Status | Keterangan                                                    |
| -------------- | ------ | ------------------------------------------------------------- |
| Database       | ✅     | Supabase + 5 tables                                           |
| Bot UI         | ✅     | 8 handlers + FSM + keyboards                                  |
| Services       | ✅     | 4 services (Order, Deposit, Payment, Voucher)                 |
| Payment        | ✅     | Tripay QRIS (sandbox + production ready)                      |
| Voucher        | ✅     | Full system                                                   |
| Webhook        | ✅     | Full handler + notifications                                  |
| User Features  | ✅     | /balance, /history, /cancel, /refund                          |
| Admin Features | ✅     | Product CRUD + User ban/unban + Broadcast + Voucher + Webhook |
| Analytics      | ✅     | /report, /topproducts, /topusers                              |

---

## 📚 All Commands

### User Commands

| Command       | Fungsi                    |
| ------------- | ------------------------- |
| /start        | Mulai bot + lihat produk  |
| /balance      | Check saldo               |
| /history      | Riwayat order (paginated) |
| /cancel ID    | Cancel pending order      |
| /refund ID    | Request refund            |
| /voucher CODE | Redeem voucher            |

### Admin Commands

| Command      | Fungsi                    |
| ------------ | ------------------------- |
| /admin       | Menu admin                |
| /stats       | Statistik bot             |
| /setqris     | Ganti QRIS method         |
| /getqris     | Lihat QRIS method aktif   |
| /addproduct  | Tambah produk             |
| /editproduct | Edit produk               |
| /delproduct  | Hapus produk              |
| /addvoucher  | Buat voucher              |
| /listvoucher | List voucher aktif        |
| /delvoucher  | Hapus voucher             |
| /banuser     | Ban user                  |
| /unbanuser   | Unban user                |
| /broadcast   | Kirim pesan ke semua user |
| /testwebhook | Simulasi callback PAID    |
| /webhookinfo | Info webhook setup        |
| /report      | Laporan penjualan         |
| /topproducts | Produk terlaris           |
| /topusers    | User top spender          |
| /restock     | Quick add stock           |
| /listproduct | List semua produk         |
| /bulkadd     | Add banyak produk paste   |
