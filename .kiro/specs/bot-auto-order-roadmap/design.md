# Design Document

## Overview

This design document describes the implementation plan for completing the T-Store Auto Order Bot. The system follows Clean Architecture with three layers: Domain (entities + interfaces), Infrastructure (database repos + payment client), and Presentation (Telegram handlers + web callbacks). Implementation is organized into 6 phases executed sequentially, each building on the previous.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                     │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │  Telegram Handlers   │  │   Web (aiohttp/FastAPI)  │ │
│  │  - start, menu       │  │   - /webhook/tripay      │ │
│  │  - order, deposit    │  │   - /webhook/telegram    │ │
│  │  - admin, voucher    │  │                          │ │
│  │  - history           │  │                          │ │
│  └──────────┬───────────┘  └────────────┬─────────────┘ │
└─────────────┼───────────────────────────┼───────────────┘
              │                           │
┌─────────────┼───────────────────────────┼───────────────┐
│             ▼         Domain Layer       ▼               │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Entities: User, Product, Order, Voucher,       │    │
│  │            DigitalCredential, Deposit            │    │
│  │  Interfaces: *Repository, PaymentGateway        │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
              │
┌─────────────┼───────────────────────────────────────────┐
│             ▼       Infrastructure Layer                  │
│  ┌────────────────────┐  ┌────────────────────────────┐ │
│  │  Database (asyncpg) │  │  Payment (Tripay httpx)   │ │
│  │  - product_repo     │  │  - create_transaction     │ │
│  │  - user_repo        │  │  - verify_signature       │ │
│  │  - order_repo       │  │  - get_payment_status     │ │
│  │  - voucher_repo     │  │                           │ │
│  │  - credential_repo  │  │                           │ │
│  └────────────────────┘  └────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### Presentation Layer

| Component | Responsibility |
|-----------|---------------|
| `telegram/handlers/start.py` | Product listing with pagination from DB |
| `telegram/handlers/menu.py` | Main menu, product lookup, user info |
| `telegram/handlers/order.py` | Order execution (saldo + direct payment) |
| `telegram/handlers/deposit.py` | Deposit FSM flow (amount → confirm → QRIS) |
| `telegram/handlers/voucher.py` | Voucher code entry and validation |
| `telegram/handlers/history.py` | Paginated order history display |
| `telegram/handlers/admin.py` | Admin panel (products, orders, users, credentials) |
| `telegram/middleware/user_middleware.py` | Auto user registration on every request |
| `telegram/middleware/error_middleware.py` | Global error handler with Indonesian messages |
| `telegram/filters/admin_filter.py` | Admin access control filter |
| `web/callbacks.py` | Tripay webhook handler (deposit + order) |

### Domain Layer

| Interface | Methods |
|-----------|---------|
| `ProductRepository` | `list_paginated(limit, offset)`, `count()`, `get_by_id(id)`, `decrement_stock(id, qty)` |
| `UserRepository` | `get_or_create(telegram_id)`, `add_balance(id, amount)`, `deduct_balance(id, amount)` |
| `OrderRepository` | `create(...)`, `get_by_id(id)`, `update_status(id, status)`, `list_by_user(user_id, limit, offset)` |
| `VoucherRepository` | `get_by_code(code)`, `validate(code)`, `increment_usage(code)` |
| `CredentialRepository` | `get_next_available(product_id)`, `mark_as_used(credential_id, order_id)` |
| `DepositRepository` | `create(...)`, `get_by_ref(ref)`, `update_status(ref, status)` |
| `PaymentGateway` | `create_qris_deposit(amount)`, `create_qris_order(order_id, amount)`, `verify_callback_signature(payload, signature)` |

### Infrastructure Layer

| Component | Technology |
|-----------|-----------|
| Database connection pool | asyncpg with Supabase PostgreSQL |
| Payment client | httpx with Tripay REST API |
| Web server | aiohttp (webhook mode) |

## Data Models

### User
```python
@dataclass
class User:
    telegram_id: int
    username: str | None
    first_name: str
    last_name: str | None
    balance: int  # IDR, always >= 0
    is_banned: bool
    created_at: datetime
    updated_at: datetime
```

### Product
```python
@dataclass
class Product:
    id: int
    name: str
    description: str
    category: str
    price: int  # IDR
    stock: int  # available units, >= 0
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

### Order
```python
@dataclass
class Order:
    id: str  # UUID or short ID
    user_id: int  # telegram_id
    product_id: int
    quantity: int
    total_price: int
    payment_method: str  # "saldo" | "qris"
    status: str  # "pending" | "paid" | "delivered" | "cancelled"
    payment_ref: str | None  # Tripay reference
    created_at: datetime
    updated_at: datetime
```

### Voucher
```python
@dataclass
class Voucher:
    id: int
    code: str
    discount_type: str  # "percentage" | "fixed"
    discount_value: int
    max_usage: int
    current_usage: int
    min_purchase: int
    expires_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

### DigitalCredential
```python
@dataclass
class DigitalCredential:
    id: int
    product_id: int
    credential_data: str  # link, email:password, license key
    is_used: bool
    delivered_to_order: str | None
    created_at: datetime
```

### Deposit
```python
@dataclass
class Deposit:
    id: int
    user_id: int
    amount: int  # IDR, >= 5000
    status: str  # "pending" | "paid" | "expired" | "failed"
    payment_method: str  # "QRIS"
    payment_ref: str | None
    tripay_url: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

## Phase 3: Database Integration & User Registration

### 3.1 Replace Mock Data with Live Database

**Changes:**
- Modify `start.py` to call `Product_Repository.list_paginated()` instead of reading from `MOCK_PRODUCTS`
- Modify `menu.py` to use `Product_Repository` for product lookup and stock reports
- Modify `order.py` to fetch product from `Product_Repository.get_by_id()`
- Inject repository instances via Aiogram middleware or bot data dict

**Implementation approach:**
- Use Aiogram's `dp["product_repo"]` pattern to inject repositories at startup
- Handlers access repos via `message.bot["product_repo"]` or middleware injection
- Keep `MOCK_PRODUCTS` as fallback only when factory returns MockRepository

### 3.2 User Registration (get_or_create)

**Changes:**
- Add middleware that calls `User_Repository.get_or_create(telegram_id)` on every message/callback
- Store user entity in handler context for downstream use
- Update "⚠️ Informasi" handler to display real balance from DB

**New files:**
- `app/presentation/telegram/middleware/user_middleware.py`

## Phase 4: Deposit & Payment Integration

### 4.1 Deposit Flow (FSM)

**New FSM states:** `DepositStates.waiting_for_amount`, `DepositStates.waiting_for_confirmation`

**Flow:**
1. User taps "💰 Deposit" → Bot asks for amount
2. User enters amount → Validate >= 5000 → Show confirmation
3. User confirms → Call Tripay API → Show QRIS + payment details
4. Tripay webhook confirms → Add balance atomically

**Changes:**
- Rewrite `app/presentation/telegram/handlers/deposit.py` with full FSM flow
- Add `DepositStates` to `states.py`
- Call `TripayClient.create_payment()` with proper signature generation

### 4.2 Tripay Client Improvements

**Changes to `app/infrastructure/payment/tripay.py`:**
- Fix signature generation to match Tripay's actual API spec (HMAC-SHA256)
- Add `create_qris_deposit()` method implementing `PaymentGateway` interface
- Add `verify_callback_signature()` for webhook validation
- Add proper error handling and response parsing

### 4.3 Payment Webhook Handler

**New/Modified files:**
- `app/presentation/web/callbacks.py` - Implement actual webhook logic
- `main.py` - Add aiohttp web server alongside polling (or switch to webhook mode)

**Webhook flow:**
1. Receive POST `/webhook/tripay`
2. Validate signature (HMAC-SHA256 with TRIPAY_API_SECRET)
3. Parse payload → determine transaction type (deposit vs order)
4. If deposit + PAID → `User_Repository.add_balance()`
5. If order + PAID → `Order_Repository.update_status()` + `Product_Repository.decrement_stock()`
6. Send Telegram notification to user
7. Trigger auto-delivery if order

## Phase 5: Real Order Execution & Auto-Delivery

### 5.1 Order Execution (Saldo Path)

**Changes to `order.py` `execute_order()`:**
```
1. Fetch user from User_Repository
2. Check balance >= total_cost
3. BEGIN transaction:
   a. User_Repository.deduct_balance(telegram_id, total_cost)
   b. Product_Repository.decrement_stock(product_id, qty)
   c. Order_Repository.create(user_id, product_id, qty, total_cost, "saldo")
4. If any step fails → rollback
5. Trigger auto-delivery
```

### 5.2 Order Execution (Direct Payment Path)

**Changes:**
```
1. Create Tripay QRIS transaction
2. Order_Repository.create(..., status="pending", payment_ref=tripay_ref)
3. Show QRIS to user
4. Wait for webhook callback to complete the order
```

### 5.3 Auto-Delivery System

**New entities:**
- `DigitalCredential` dataclass in `entities.py` (id, product_id, credential_data, is_used, delivered_to_order_id)

**New infrastructure:**
- `app/infrastructure/database/credential_repo.py` - `CredentialRepository`

**Flow:**
1. On order "paid" → fetch next unused credential for product
2. Mark credential as used + link to order
3. Send credential to user via Telegram
4. Update order status to "delivered"

## Phase 6: Voucher System & Order History

### 6.1 Voucher System

**New entities:**
- `Voucher` dataclass (id, code, discount_type, discount_value, max_usage, current_usage, expires_at, is_active)

**New infrastructure:**
- `app/infrastructure/database/voucher_repo.py`
- Migration `002_voucher_credentials.sql`

**New handlers:**
- `app/presentation/telegram/handlers/voucher.py`

**Integration with checkout:**
- Add optional voucher step in order FSM before confirmation
- Calculate discount and show adjusted total

### 6.2 Order History

**New handler:**
- `app/presentation/telegram/handlers/history.py`
- Add "📜 Riwayat" button to reply keyboard

**Flow:**
1. User taps "📜 Riwayat" → Show paginated order list
2. User selects order → Show detail + credentials if delivered

## Phase 7: Admin Panel

### 7.1 Admin Access Control

**Config:** `ADMIN_IDS` list in settings.py (comma-separated telegram IDs from env)

**New middleware/filter:**
- `app/presentation/telegram/filters/admin_filter.py` - Custom Aiogram filter

### 7.2 Admin Handlers

**New file:** `app/presentation/telegram/handlers/admin.py`

**Sub-flows (each with own FSM states):**
- Product management: list/add/edit/toggle active
- Order management: view by status, manual status update
- User management: view/adjust balance/ban
- Credential management: bulk upload for product

## Phase 8: Error Handling & Deployment

### 8.1 Global Error Handler

**Implementation:**
- Aiogram outer middleware that wraps all handlers in try/except
- Log full traceback with structured logging
- Return user-friendly Indonesian error messages
- Specific handling for known exceptions (DB timeout, API errors)

### 8.2 Database Resilience

**Implementation:**
- Connection health check on pool acquire failure
- Exponential backoff reconnection (1s, 2s, 4s, 8s, 16s → fallback to mock)
- Circuit breaker pattern for Tripay API calls

### 8.3 Deployment

**New files:**
- `Dockerfile` - Multi-stage build (slim Python image)
- `docker-compose.yml` - Bot + optional local PostgreSQL for dev
- `.env.example` - Template with all required env vars documented

**Webhook mode:**
- Add aiohttp web app that handles both `/webhook/telegram` and `/webhook/tripay`
- Configurable via `BOT_MODE=polling|webhook` env var

## Database Migrations

### Migration 002: Vouchers & Credentials

```sql
CREATE TABLE IF NOT EXISTS vouchers (
    id          BIGSERIAL PRIMARY KEY,
    code        VARCHAR(32) UNIQUE NOT NULL,
    discount_type VARCHAR(16) NOT NULL CHECK (discount_type IN ('percentage', 'fixed')),
    discount_value BIGINT NOT NULL CHECK (discount_value > 0),
    max_usage   INTEGER NOT NULL DEFAULT 1,
    current_usage INTEGER NOT NULL DEFAULT 0,
    min_purchase BIGINT DEFAULT 0,
    expires_at  TIMESTAMPTZ,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS digital_credentials (
    id              BIGSERIAL PRIMARY KEY,
    product_id      BIGINT NOT NULL REFERENCES products(id),
    credential_data TEXT NOT NULL,
    is_used         BOOLEAN NOT NULL DEFAULT FALSE,
    delivered_to_order VARCHAR(32) REFERENCES orders(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credentials_product_available
    ON digital_credentials(product_id)
    WHERE is_used = FALSE;
```

### Migration 003: Deposits Table

```sql
CREATE TABLE IF NOT EXISTS deposits (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(telegram_id),
    amount          BIGINT NOT NULL CHECK (amount >= 5000),
    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'paid', 'expired', 'failed')),
    payment_method  VARCHAR(32) NOT NULL DEFAULT 'QRIS',
    payment_ref     VARCHAR(128),
    tripay_url      TEXT,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deposits_user ON deposits(user_id);
CREATE INDEX IF NOT EXISTS idx_deposits_ref ON deposits(payment_ref);
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Atomic Balance Deduction

*For any* valid deduction operation with a given amount, `balance_after = balance_before - amount` AND the operation fails atomically if `balance_before < amount` (balance never goes negative).

**Validates: Requirements 4.4**

### Property 2: Atomic Stock Decrement

*For any* valid stock decrement with a given quantity, `stock_after = stock_before - qty` AND the operation fails atomically if `stock_before < qty` (stock never goes negative).

**Validates: Requirements 4.5**

### Property 3: User get_or_create Idempotence

*For any* telegram_id, calling `get_or_create(telegram_id)` multiple times always returns the same user record without creating duplicates.

**Validates: Requirements 2.1, 2.2**

### Property 4: Voucher Discount Bounds

*For any* voucher configuration and original price, the discounted price satisfies `0 <= discounted_price <= original_price`. A percentage discount of X% reduces price by exactly X% (floored to int). A fixed discount reduces price by the fixed amount or to 0, whichever is greater.

**Validates: Requirements 7.4, 7.5**

### Property 5: Webhook Signature Validation

*For any* webhook payload and secret, a payload signed with the correct secret always passes validation, and a payload signed with any other secret always fails validation.

**Validates: Requirements 5.2, 5.3**

### Property 6: Deposit Amount Validation

*For any* integer amount, amounts >= 5000 are accepted and amounts < 5000 are rejected. Non-positive amounts are always rejected.

**Validates: Requirements 3.2, 3.3**

### Property 7: Order History Pagination

*For any* set of user orders and pagination parameters (limit, offset), `len(result) <= limit`, results are sorted by created_at descending, and paginating through all pages returns all orders exactly once.

**Validates: Requirements 8.1**

### Property 8: Database Reconnection Backoff

*For any* sequence of connection failures, reconnection attempts follow exponential backoff (delay doubles each attempt), total attempts never exceed 5, and after 5 failures the system falls back to mock repositories.

**Validates: Requirements 11.7**

## Error Handling

### Error Categories and Responses

| Error Type | User Message (Indonesian) | System Action |
|-----------|--------------------------|---------------|
| Database connection failure | "Maaf, terjadi gangguan sistem. Silakan coba lagi nanti." | Log error, attempt reconnect with backoff |
| Tripay API failure | "Layanan pembayaran sedang tidak tersedia. Silakan coba beberapa saat lagi." | Log error, circuit breaker tracks failure |
| Insufficient balance | "Saldo Anda tidak mencukupi. Silakan deposit terlebih dahulu." | No retry needed |
| Out of stock | "Maaf, produk ini sudah habis." | Cancel order, refund if balance deducted |
| Invalid voucher | "Kode voucher tidak valid / sudah kadaluarsa / sudah mencapai batas penggunaan." | Specific reason shown |
| Webhook signature invalid | HTTP 403 response | Log IP and payload hash |
| Unexpected exception | "Terjadi kesalahan. Tim kami sudah diberitahu." | Log full traceback, alert admin |

### Resilience Patterns

1. **Database Reconnection**: Exponential backoff (1s, 2s, 4s, 8s, 16s), max 5 retries, fallback to mock repositories
2. **Tripay Circuit Breaker**: Open after 3 consecutive failures, half-open after 30s cooldown, close on success
3. **Atomic Operations**: All balance/stock mutations use SQL guards (`WHERE balance >= amount`) to prevent negative values
4. **Transaction Rollback**: If stock decrement fails after balance deduction, refund balance and cancel order

### Error Middleware

Global error middleware wraps all handlers:
- Catches unhandled exceptions
- Logs structured error with context (user_id, handler, state)
- Returns generic user-friendly message
- Does not expose stack traces or internal details to users

## Testing Strategy

### Unit Tests (Example-Based)

- **Handlers**: Test FSM state transitions with mocked repositories
- **Repositories**: Test SQL query construction and result mapping
- **Payment client**: Test signature generation and response parsing
- **Admin filter**: Test access control with admin/non-admin IDs
- **Error middleware**: Test that exceptions produce correct user messages

### Property-Based Tests (Hypothesis)

Library: **Hypothesis** (Python PBT library)
Configuration: Minimum 100 iterations per property

| Property | Test Description | Tag |
|----------|-----------------|-----|
| Property 1 | Generate random (balance, amount) pairs, verify atomic deduction invariant | `Feature: bot-auto-order-roadmap, Property 1: Atomic Balance Deduction` |
| Property 2 | Generate random (stock, qty) pairs, verify atomic decrement invariant | `Feature: bot-auto-order-roadmap, Property 2: Atomic Stock Decrement` |
| Property 3 | Generate random telegram_ids, call get_or_create multiple times, verify idempotence | `Feature: bot-auto-order-roadmap, Property 3: User get_or_create Idempotence` |
| Property 4 | Generate random voucher configs and prices, verify discount bounds | `Feature: bot-auto-order-roadmap, Property 4: Voucher Discount Bounds` |
| Property 5 | Generate random payloads and secrets, verify signature validation round-trip | `Feature: bot-auto-order-roadmap, Property 5: Webhook Signature Validation` |
| Property 6 | Generate random integers, verify deposit amount acceptance/rejection | `Feature: bot-auto-order-roadmap, Property 6: Deposit Amount Validation` |
| Property 7 | Generate random order sets and pagination params, verify pagination invariants | `Feature: bot-auto-order-roadmap, Property 7: Order History Pagination` |
| Property 8 | Simulate connection failure sequences, verify backoff timing and max retries | `Feature: bot-auto-order-roadmap, Property 8: Database Reconnection Backoff` |

### Integration Tests

- **Database**: Test actual CRUD operations against a test PostgreSQL instance
- **Tripay webhook**: Test full webhook flow with signed payloads
- **End-to-end order flow**: Test saldo deduction → stock decrement → credential delivery
- **Deposit flow**: Test amount validation → Tripay call → webhook confirmation → balance update

### Test Organization

```
tests/
├── unit/
│   ├── test_balance_deduction.py
│   ├── test_stock_decrement.py
│   ├── test_voucher_discount.py
│   ├── test_deposit_validation.py
│   ├── test_signature_validation.py
│   └── test_reconnection_backoff.py
├── property/
│   ├── test_balance_properties.py
│   ├── test_stock_properties.py
│   ├── test_idempotence_properties.py
│   ├── test_voucher_properties.py
│   ├── test_signature_properties.py
│   ├── test_deposit_properties.py
│   ├── test_pagination_properties.py
│   └── test_reconnection_properties.py
└── integration/
    ├── test_database_repos.py
    ├── test_tripay_webhook.py
    └── test_order_flow.py
```

## File Structure (New/Modified)

```
app/
├── domain/
│   ├── entities.py              # + Voucher, DigitalCredential, Deposit
│   └── interfaces.py            # + VoucherRepository, CredentialRepository, DepositRepository
├── infrastructure/
│   ├── database/
│   │   ├── connection.py        # + reconnection logic with backoff
│   │   ├── factory.py           # + voucher_repo, credential_repo, deposit_repo
│   │   ├── voucher_repo.py      # NEW
│   │   ├── credential_repo.py   # NEW
│   │   └── deposit_repo.py      # NEW
│   └── payment/
│       └── tripay.py            # Rewrite with proper HMAC + webhook verification
├── presentation/
│   ├── telegram/
│   │   ├── handlers/
│   │   │   ├── start.py         # Modified: use Product_Repository
│   │   │   ├── menu.py          # Modified: use Product_Repository
│   │   │   ├── order.py         # Modified: real execution logic
│   │   │   ├── deposit.py       # Rewrite: full FSM deposit flow
│   │   │   ├── voucher.py       # NEW
│   │   │   ├── history.py       # NEW
│   │   │   └── admin.py         # NEW
│   │   ├── middleware/
│   │   │   ├── user_middleware.py    # NEW: auto get_or_create
│   │   │   └── error_middleware.py   # NEW: global error handler
│   │   ├── filters/
│   │   │   └── admin_filter.py  # NEW
│   │   └── states.py            # + DepositStates, VoucherStates, AdminStates
│   └── web/
│       └── callbacks.py         # Rewrite: real webhook handling
├── main.py                      # + web server, middleware registration
config/
├── settings.py                  # + ADMIN_IDS, BOT_MODE
migrations/
├── 002_voucher_credentials.sql  # NEW
├── 003_deposits.sql             # NEW
Dockerfile                       # NEW
docker-compose.yml               # NEW
.env.example                     # NEW
```
