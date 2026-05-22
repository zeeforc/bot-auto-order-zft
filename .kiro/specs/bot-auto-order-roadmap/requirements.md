# Requirements Document

## Introduction

T-Store Auto Order Bot adalah Telegram bot untuk otomatisasi penjualan produk digital (akun, lisensi, subscription) yang beroperasi 24/7. Bot ini sudah memiliki skeleton dasar (Phase 1-2) termasuk command /start, product listing, order flow dengan FSM, dan schema database. Dokumen ini mendefinisikan requirements untuk semua fitur yang tersisa: koneksi database live, user registration, deposit/top-up via Tripay, eksekusi order real, payment webhook, voucher system, admin panel, order history, auto-delivery, error handling, dan deployment.

## Glossary

- **Bot**: Telegram bot T-Store Auto Order yang berjalan menggunakan Aiogram 3.x
- **User**: Pengguna Telegram yang berinteraksi dengan Bot
- **Admin**: Pengelola toko yang memiliki akses ke panel administrasi
- **Product**: Produk digital (akun, lisensi, subscription) yang dijual melalui Bot
- **Order**: Transaksi pembelian produk oleh User
- **Balance**: Saldo internal User dalam satuan Rupiah (IDR) yang tersimpan di database
- **Deposit**: Proses pengisian Balance melalui payment gateway
- **Tripay**: Payment gateway pihak ketiga yang menyediakan QRIS dan Virtual Account
- **QRIS**: Quick Response Code Indonesian Standard, metode pembayaran scan QR
- **Webhook**: HTTP callback dari Tripay ke Bot untuk notifikasi status pembayaran
- **Voucher**: Kode diskon yang dapat digunakan User saat checkout
- **Auto_Delivery**: Pengiriman otomatis kredensial produk digital setelah pembayaran dikonfirmasi
- **Stock**: Jumlah unit produk digital yang tersedia untuk dijual
- **FSM**: Finite State Machine, mekanisme pengelolaan state percakapan di Aiogram
- **Product_Repository**: Interface abstrak untuk akses data produk
- **User_Repository**: Interface abstrak untuk akses data user
- **Order_Repository**: Interface abstrak untuk akses data order
- **Connection_Pool**: Pool koneksi asyncpg ke PostgreSQL/Supabase
- **Digital_Credential**: Data akun/lisensi yang dikirim ke User setelah pembelian (link, email, password, license key)

## Requirements

### Requirement 1: Database Connection & Live Data

**User Story:** As a developer, I want the Bot to connect to Supabase PostgreSQL and serve real product data, so that the store operates with actual inventory instead of mock data.

#### Acceptance Criteria

1. WHEN the Bot starts, THE Connection_Pool SHALL initialize an asyncpg connection pool to the configured DATABASE_URL
2. IF the Connection_Pool fails to connect at startup, THEN THE Bot SHALL log the error and fall back to Mock repositories with a warning message in logs
3. WHEN a User requests the product list, THE Product_Repository SHALL fetch products from the database with pagination (limit/offset)
4. WHEN a User selects a product by number, THE Product_Repository SHALL retrieve the product detail from the database by ID
5. THE Bot SHALL replace all references to MOCK_PRODUCTS with calls to Product_Repository within handlers

---

### Requirement 2: User Registration

**User Story:** As a User, I want to be automatically registered when I first interact with the Bot, so that my balance and order history are tracked.

#### Acceptance Criteria

1. WHEN a User sends /start for the first time, THE User_Repository SHALL create a new user record with telegram_id, username, first_name, and last_name
2. WHEN a User sends /start and already exists in the database, THE User_Repository SHALL return the existing user record without creating a duplicate
3. WHEN a User record is created, THE Bot SHALL set the initial Balance to 0 and is_banned to false
4. IF the User_Repository fails to create or retrieve a user, THEN THE Bot SHALL respond with a user-friendly error message and log the exception

---

### Requirement 3: Deposit Flow (Balance Top-Up via Tripay)

**User Story:** As a User, I want to top up my Balance using QRIS or Virtual Account, so that I can purchase products using internal saldo.

#### Acceptance Criteria

1. WHEN a User taps "💰 Deposit", THE Bot SHALL prompt the User to enter a deposit amount
2. WHILE the User is in the deposit FSM state, THE Bot SHALL validate that the entered amount is a positive integer of at least Rp 5,000
3. IF the User enters an invalid deposit amount, THEN THE Bot SHALL display an error message specifying the minimum deposit requirement
4. WHEN a valid deposit amount is confirmed, THE Bot SHALL call Tripay API to create a QRIS payment transaction with the specified amount
5. WHEN Tripay returns a successful payment creation response, THE Bot SHALL display the QRIS image, payment reference ID, total amount including fee, and expiration time to the User
6. IF Tripay API returns an error during payment creation, THEN THE Bot SHALL inform the User that payment creation failed and suggest retrying
7. WHEN a deposit payment is confirmed via Webhook, THE User_Repository SHALL add the deposited amount to the User Balance atomically

---

### Requirement 4: Real Order Execution

**User Story:** As a User, I want my order to actually deduct stock and balance when I confirm a purchase, so that I receive the product I paid for.

#### Acceptance Criteria

1. WHEN a User confirms an order with method "saldo", THE Bot SHALL verify that the User Balance is sufficient for the total price
2. IF the User Balance is insufficient for a saldo order, THEN THE Bot SHALL display a message indicating insufficient balance and suggest depositing
3. WHEN a saldo order is confirmed and balance is sufficient, THE Order_Repository SHALL create an order record with status "paid"
4. WHEN a saldo order is confirmed and balance is sufficient, THE User_Repository SHALL deduct the total price from User Balance atomically using a single SQL UPDATE with guard `balance >= amount`
5. WHEN a saldo order is confirmed and balance is sufficient, THE Product_Repository SHALL decrement the product stock atomically using a single SQL UPDATE with guard `stock >= qty`
6. IF the atomic stock decrement fails (stock insufficient), THEN THE Bot SHALL cancel the order and refund the deducted balance
7. WHEN a User confirms an order with method "now" (direct payment), THE Bot SHALL create a Tripay QRIS transaction for the order total plus fee
8. WHEN a direct payment order is created, THE Order_Repository SHALL create an order record with status "pending" and store the Tripay payment reference

---

### Requirement 5: Payment Webhook Handler

**User Story:** As a system operator, I want Tripay payment callbacks to be processed automatically, so that deposits and direct orders are confirmed without manual intervention.

#### Acceptance Criteria

1. THE Bot SHALL expose an HTTP endpoint at `/webhook/tripay` that accepts POST requests from Tripay
2. WHEN a webhook request is received, THE Bot SHALL validate the request signature using the configured TRIPAY_API_SECRET
3. IF the webhook signature validation fails, THEN THE Bot SHALL respond with HTTP 403 and log the invalid attempt
4. WHEN a valid webhook with status "PAID" is received for a deposit transaction, THE User_Repository SHALL add the payment amount to the User Balance atomically
5. WHEN a valid webhook with status "PAID" is received for a direct order transaction, THE Order_Repository SHALL update the order status from "pending" to "paid"
6. WHEN a valid webhook with status "PAID" is received for a direct order, THE Product_Repository SHALL decrement the product stock atomically
7. IF the stock decrement fails during webhook processing, THEN THE Bot SHALL mark the order as "cancelled" and initiate a refund flag
8. WHEN a payment is confirmed (deposit or order), THE Bot SHALL send a Telegram notification to the User confirming the successful payment
9. WHEN a valid webhook with status "EXPIRED" or "FAILED" is received, THE Order_Repository SHALL update the order status to "cancelled"

---

### Requirement 6: Auto-Delivery of Digital Products

**User Story:** As a User, I want to receive my purchased digital product credentials immediately after payment is confirmed, so that I can use the product without waiting.

#### Acceptance Criteria

1. WHEN an order status transitions to "paid", THE Bot SHALL retrieve the Digital_Credential associated with the purchased product
2. WHEN a Digital_Credential is available, THE Bot SHALL send the credential details (link, account info, license key) to the User via Telegram message
3. IF no Digital_Credential is available for the product, THEN THE Bot SHALL notify the User that delivery is pending and alert the Admin
4. WHEN a Digital_Credential is delivered, THE Order_Repository SHALL update the order status to "delivered"
5. THE Bot SHALL format the delivery message with product name, credential details, and usage instructions

---

### Requirement 7: Voucher System

**User Story:** As a User, I want to apply discount vouchers during checkout, so that I can get products at a reduced price.

#### Acceptance Criteria

1. WHEN a User taps "🎫 Voucher" from the main menu, THE Bot SHALL prompt the User to enter a voucher code
2. WHEN a voucher code is submitted, THE Bot SHALL validate that the code exists, is active, has not expired, and has remaining usage quota
3. IF the voucher code is invalid or expired, THEN THE Bot SHALL display a specific error message indicating the reason
4. WHEN a valid voucher is applied during checkout, THE Bot SHALL calculate the discounted total price based on the voucher type (percentage or fixed amount)
5. THE Bot SHALL enforce that a voucher discount does not reduce the total price below zero
6. WHEN an order with a voucher is completed, THE Bot SHALL decrement the voucher usage count atomically
7. WHILE a voucher has reached its maximum usage count, THE Bot SHALL reject further applications of that voucher code

---

### Requirement 8: Order History

**User Story:** As a User, I want to view my past orders, so that I can track my purchases and re-access delivered credentials.

#### Acceptance Criteria

1. WHEN a User requests order history, THE Order_Repository SHALL retrieve the User orders sorted by creation date descending with pagination (10 per page)
2. THE Bot SHALL display each order with: order ID, product name, quantity, total price, status, and creation date
3. WHEN a User selects a specific order from history, THE Bot SHALL display the full order detail including payment method and delivered credentials if available
4. IF the User has no orders, THEN THE Bot SHALL display a message indicating no purchase history exists

---

### Requirement 9: Admin Panel

**User Story:** As an Admin, I want to manage products, view orders, and manage users through the Bot, so that I can operate the store without direct database access.

#### Acceptance Criteria

1. WHEN a User sends /admin, THE Bot SHALL verify that the User telegram_id is in the configured admin list
2. IF a non-admin User sends /admin, THEN THE Bot SHALL respond with an access denied message
3. WHEN an Admin accesses the admin panel, THE Bot SHALL display an admin menu with options: Manage Products, View Orders, Manage Users, Add Stock Credentials
4. WHEN an Admin selects "Manage Products", THE Bot SHALL allow adding new products with name, description, category, and price
5. WHEN an Admin selects "Manage Products", THE Bot SHALL allow editing existing product details (name, price, stock, is_active status)
6. WHEN an Admin selects "View Orders", THE Bot SHALL display recent orders with filtering by status (pending, paid, delivered, cancelled)
7. WHEN an Admin selects "Manage Users", THE Bot SHALL allow viewing user details, adjusting user balance, and banning/unbanning users
8. WHEN an Admin selects "Add Stock Credentials", THE Bot SHALL allow uploading Digital_Credentials (links, accounts) for a specific product in bulk

---

### Requirement 10: Error Handling & User-Friendly Messages

**User Story:** As a User, I want to receive clear and helpful error messages when something goes wrong, so that I understand what happened and what to do next.

#### Acceptance Criteria

1. IF a database query fails during any handler execution, THEN THE Bot SHALL respond with a generic user-friendly error message without exposing technical details
2. IF a Tripay API call fails, THEN THE Bot SHALL inform the User that the payment service is temporarily unavailable and suggest retrying later
3. WHEN an unexpected exception occurs in any handler, THE Bot SHALL catch the exception, log the full traceback, and respond with a generic error message
4. THE Bot SHALL implement a global error handler middleware that catches unhandled exceptions across all routers
5. IF a User attempts to purchase a product that has become out of stock during the checkout flow, THEN THE Bot SHALL inform the User that the product is no longer available

---

### Requirement 11: Deployment & Production Readiness

**User Story:** As a system operator, I want the Bot to be deployable to a VPS or cloud platform with proper configuration, so that it runs reliably in production 24/7.

#### Acceptance Criteria

1. THE Bot SHALL support configuration via environment variables for all secrets (BOT_TOKEN, DATABASE_URL, TRIPAY keys, WEBHOOK_SECRET)
2. THE Bot SHALL include a Dockerfile that builds a production-ready container image
3. THE Bot SHALL implement graceful shutdown that closes the Connection_Pool and HTTP clients when receiving SIGTERM
4. THE Bot SHALL support both polling mode (development) and webhook mode (production) for receiving Telegram updates
5. WHEN running in webhook mode, THE Bot SHALL expose an HTTP server (aiohttp/FastAPI) that handles both Telegram webhook updates and Tripay payment callbacks
6. THE Bot SHALL include structured logging with configurable log levels (DEBUG, INFO, WARNING, ERROR)
7. IF the database connection is lost during operation, THEN THE Bot SHALL attempt to reconnect with exponential backoff up to 5 retries before falling back to mock repositories
