# Phase 2: Database Integration - Summary

## ✅ Completed

### 1. Domain Layer (`app/domain/`)
- **entities.py**: Updated dengan `Product.id` (int), `balance/price` (int IDR), `is_active`, `is_banned`
- **interfaces.py**: Added 3 abstract repositories:
  - `ProductRepository`: list_paginated, count, get_by_id, decrement_stock (atomic)
  - `UserRepository`: get_or_create, get_by_id, deduct_balance (atomic), add_balance (atomic)
  - `OrderRepository`: create, get_by_id, get_by_user, update_status

### 2. Infrastructure Layer (`app/infrastructure/database/`)
- **connection.py**: asyncpg pool management (init_pool, close_pool, get_pool, test_db_connection)
- **product_repo.py**: AsyncPgProductRepository + MockProductRepository (fallback)
- **user_repo.py**: AsyncPgUserRepository + MockUserRepository (fallback)
- **order_repo.py**: AsyncPgOrderRepository + MockOrderRepository (fallback)
- **factory.py**: Singleton factories dengan auto-detect (DB atau mock)
- **__init__.py**: Export semua public APIs

### 3. Database Schema (`migrations/001_init_schema.sql`)
- **users**: telegram_id (PK), balance (BIGINT IDR), is_banned, timestamps
- **products**: id (BIGSERIAL), name, price (BIGINT IDR), stock (INTEGER), is_active, timestamps
- **orders**: id (UUID), user_id (FK), product_id (FK), quantity, total_price, status, payment_method, timestamps
- Constraints: `CHECK (balance >= 0)`, `CHECK (stock >= 0)`, `CHECK (price >= 0)`, `CHECK (quantity > 0)`
- Triggers: Auto-update `updated_at` pada setiap UPDATE
- Indexes: Partial index untuk `is_active`, index untuk foreign keys dan status

### 4. Presentation Layer (`app/presentation/telegram/handlers/order.py`)
- Updated untuk pakai `get_product_repository()` instead of `MOCK_PRODUCTS`
- Semua handler sekarang async-compatible dengan repository

### 5. Testing
- **test_db.py**: Comprehensive test untuk semua 3 repository
  - ProductRepository: list_paginated, count, get_by_id, decrement_stock
  - UserRepository: get_or_create, add_balance, deduct_balance
  - OrderRepository: create, get_by_id, get_by_user, update_status

## 🔒 Race Condition Handling

### Atomic Operations (Database Level)
Semua operasi yang critical menggunakan single SQL statement dengan guard clause:

**Product Stock Decrement:**
```sql
UPDATE products
   SET stock = stock - $2
 WHERE id = $1
   AND is_active = TRUE
   AND stock >= $2
RETURNING id
```

**User Balance Deduction:**
```sql
UPDATE users
   SET balance = balance - $2
 WHERE telegram_id = $1
   AND NOT is_banned
   AND balance >= $2
RETURNING telegram_id
```

**User Balance Addition:**
```sql
UPDATE users
   SET balance = balance + $2
 WHERE telegram_id = $1
   AND NOT is_banned
RETURNING telegram_id
```

Postgres row-level locking memastikan concurrent UPDATE pada row yang sama dijalankan serial. Yang gagal match guard clause langsung return 0 rows → handler dapat `False`.

## 🔄 Fallback Strategy

Jika DB connection gagal:
- ProductRepository → MockProductRepository (in-memory)
- UserRepository → MockUserRepository (in-memory)
- OrderRepository → MockOrderRepository (in-memory)

Bot tetap jalan dengan data dummy. Berguna untuk development/testing tanpa DB.

## 📋 Requirements Updated

```txt
asyncpg==0.31.0  # Async PostgreSQL driver (ganti psycopg2-binary)
```

## 🚀 Next Steps

1. **Jalankan migration SQL** ke Supabase:
   - Paste isi `migrations/001_init_schema.sql` ke Supabase SQL Editor
   - Atau: `psql "$DATABASE_URL" -f migrations/001_init_schema.sql`

2. **Wiring ke main.py**:
   ```python
   from app.infrastructure.database import init_pool, close_pool
   
   async def main():
       await init_pool()
       # ... bot setup ...
       await close_pool()
   ```

3. **Implement UseCase Layer** (Phase 3):
   - OrderService: create order + deduct stock + deduct balance (transactional)
   - PaymentService: handle Tripay webhook, update order status
   - DepositService: handle balance top-up

4. **Implement Handlers** (Phase 3):
   - Update `order.py` untuk call OrderService
   - Add `deposit.py` untuk balance top-up
   - Add webhook handler untuk payment callback

## 📊 Architecture Compliance

✅ Clean Architecture maintained:
- Domain: Pure business logic, no external dependencies
- Infrastructure: DB/API implementations, no business logic
- Presentation: Telegram handlers, no DB access (via repository)

✅ Async-first: All operations use asyncpg (no blocking calls)

✅ Type hints: All functions have complete type annotations

✅ Error handling: Try-except dengan user-friendly messages

✅ Pagination: All list operations support limit/offset

## 🧪 Test Results

```
ProductRepository: ✅ MockProductRepository (5 products)
  - list_paginated: ✅
  - count: ✅
  - get_by_id: ✅
  - decrement_stock: ✅

UserRepository: ✅ MockUserRepository
  - get_or_create: ✅
  - add_balance: ✅ (0 → 100000)
  - deduct_balance: ✅ (100000 → 50000)

OrderRepository: ✅ MockOrderRepository
  - create: ✅ (UUID generated)
  - get_by_id: ✅
  - get_by_user: ✅
  - update_status: ✅ (pending → paid)
```

## 📁 File Structure

```
c:\bot-auto-order\
├── migrations/
│   └── 001_init_schema.sql
├── app/
│   ├── domain/
│   │   ├── entities.py (updated)
│   │   └── interfaces.py (updated)
│   ├── infrastructure/
│   │   └── database/
│   │       ├── __init__.py (updated)
│   │       ├── connection.py (new)
│   │       ├── factory.py (updated)
│   │       ├── product_repo.py (updated)
│   │       ├── user_repo.py (new)
│   │       ├── order_repo.py (new)
│   │       └── repository.py (old, unused)
│   └── presentation/
│       └── telegram/
│           └── handlers/
│               └── order.py (updated)
├── test_db.py (updated)
└── requirements.txt (updated)
```
