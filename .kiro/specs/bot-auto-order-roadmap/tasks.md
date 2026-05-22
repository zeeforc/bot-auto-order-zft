# Implementation Plan: Bot Auto Order Roadmap

## Overview

This implementation plan covers the completion of the T-Store Auto Order Bot from Phase 3 through Phase 8. Each phase builds on the previous, starting with database integration and ending with deployment readiness. The plan covers: live database connection, user registration, deposit/payment via Tripay, real order execution with auto-delivery, voucher system, admin panel, error handling, and containerized deployment.

## Tasks

### Phase 3: Database Integration & User Registration

- [ ] 1. Create user middleware (`app/presentation/telegram/middleware/user_middleware.py`) that calls `User_Repository.get_or_create(telegram_id)` on every incoming message/callback and stores the user entity in handler data
- [ ] 2. Register repositories in bot startup (`main.py`): call `init_pool()`, instantiate repos via factory, store in `dp["product_repo"]`, `dp["user_repo"]`, `dp["order_repo"]`
- [ ] 3. Refactor `start.py` to replace `MOCK_PRODUCTS` with `Product_Repository.list_paginated()` and `Product_Repository.count()` for pagination
- [ ] 4. Refactor `menu.py` to fetch products from `Product_Repository` instead of importing `MOCK_PRODUCTS` from start.py
- [ ] 5. Refactor `order.py` to fetch product from `Product_Repository.get_by_id()` instead of `_get_product()` helper using MOCK_PRODUCTS
- [ ] 6. Update "⚠️ Informasi" handler in `menu.py` to display real user balance and stats from the database
- [ ] 7. Fix Supabase connection: verify DATABASE_URL format, test connectivity, handle SSL/pooler mode if needed

### Phase 4: Deposit & Payment Integration

- [ ] 8. Add `DepositStates` (waiting_for_amount, waiting_for_confirmation) to `app/presentation/telegram/states.py`
- [ ] 9. Create migration `002_voucher_credentials.sql` with vouchers and digital_credentials tables
- [ ] 10. Create migration `003_deposits.sql` with deposits table
- [ ] 11. Rewrite `app/presentation/telegram/handlers/deposit.py` with full FSM flow: prompt amount → validate >= 5000 → confirm → call Tripay → show QRIS
- [ ] 12. Fix `app/infrastructure/payment/tripay.py`: implement proper HMAC-SHA256 signature per Tripay API docs, add `create_qris_deposit()`, add `verify_callback_signature()`
- [ ] 13. Create `app/infrastructure/database/deposit_repo.py` implementing deposit CRUD (create, get_by_ref, update_status)
- [ ] 14. Implement webhook handler in `app/presentation/web/callbacks.py`: validate signature, parse payload, route to deposit or order processing, send Telegram notification
- [ ] 15. Add aiohttp web server to `main.py` that runs alongside bot polling, exposing `/webhook/tripay` endpoint

### Phase 5: Real Order Execution & Auto-Delivery

- [ ] 16. Rewrite `execute_order()` in `order.py` for saldo path: fetch user balance → verify sufficient → atomic deduct balance + decrement stock + create order in single transaction
- [ ] 17. Implement direct payment (Buy Now) path in `order.py`: create Tripay transaction → create pending order with payment_ref → show QRIS to user
- [ ] 18. Add `DigitalCredential` entity to `app/domain/entities.py` and `CredentialRepository` interface to `interfaces.py`
- [ ] 19. Create `app/infrastructure/database/credential_repo.py` with methods: `get_next_available(product_id)`, `mark_as_used(credential_id, order_id)`
- [ ] 20. Implement auto-delivery logic: on order status "paid" → fetch credential → send to user → mark delivered. Handle missing credentials by notifying admin
- [ ] 21. Add rollback logic: if stock decrement fails after balance deduction, refund the balance and cancel the order

### Phase 6: Voucher System & Order History

- [ ] 22. Add `Voucher` entity to `app/domain/entities.py` and `VoucherRepository` interface to `interfaces.py`
- [ ] 23. Create `app/infrastructure/database/voucher_repo.py` with methods: `get_by_code()`, `validate()`, `increment_usage()`
- [ ] 24. Create `app/presentation/telegram/handlers/voucher.py`: prompt code entry → validate → show discount preview → store in FSM for checkout
- [ ] 25. Integrate voucher into order checkout flow: add optional voucher step before confirmation, calculate discounted total
- [ ] 26. Create `app/presentation/telegram/handlers/history.py`: paginated order list → detail view with credentials
- [ ] 27. Add "📜 Riwayat" button to reply keyboard and register history router

### Phase 7: Admin Panel

- [ ] 28. Add `ADMIN_IDS` configuration to `config/settings.py` (comma-separated env var)
- [ ] 29. Create `app/presentation/telegram/filters/admin_filter.py` with custom Aiogram filter checking telegram_id against ADMIN_IDS
- [ ] 30. Create `app/presentation/telegram/handlers/admin.py` with /admin command and admin menu (Manage Products, View Orders, Manage Users, Add Credentials)
- [ ] 31. Implement admin product management: list products, add new product (FSM), edit product fields, toggle is_active
- [ ] 32. Implement admin order management: view orders filtered by status, manual status update
- [ ] 33. Implement admin user management: search user, view details, adjust balance, ban/unban
- [ ] 34. Implement admin credential upload: select product → paste credentials (one per line) → bulk insert into digital_credentials table

### Phase 8: Error Handling & Deployment

- [ ] 35. Create `app/presentation/telegram/middleware/error_middleware.py`: global try/except wrapper, structured logging, user-friendly error responses in Indonesian
- [ ] 36. Add database reconnection logic to `connection.py`: exponential backoff (1s, 2s, 4s, 8s, 16s), max 5 retries, fallback to mock repos
- [ ] 37. Add circuit breaker for Tripay API calls: track failures, open circuit after 3 consecutive failures, half-open after 30s cooldown
- [ ] 38. Create `Dockerfile` (multi-stage build with python:3.11-slim) and `docker-compose.yml` for local dev
- [ ] 39. Add webhook mode support: configurable via `BOT_MODE` env var, aiohttp server handles both Telegram updates and Tripay callbacks in webhook mode
- [ ] 40. Implement graceful shutdown: handle SIGTERM, close asyncpg pool, close httpx clients, stop polling/webhook server
- [ ] 41. Create `.env.example` with all required environment variables documented with descriptions

## Task Dependency Graph

```json
{
  "waves": [
    {
      "name": "Wave 1: Database Foundation",
      "tasks": ["7"]
    },
    {
      "name": "Wave 2: Repository Setup",
      "tasks": ["2"]
    },
    {
      "name": "Wave 3: Handler Refactoring & User Middleware",
      "tasks": ["1", "3", "4", "5"]
    },
    {
      "name": "Wave 4: User Info & States & Migrations",
      "tasks": ["6", "8", "9", "10"]
    },
    {
      "name": "Wave 5: Payment & Deposit Core",
      "tasks": ["12", "13"]
    },
    {
      "name": "Wave 6: Deposit Flow & Webhook",
      "tasks": ["11", "14"]
    },
    {
      "name": "Wave 7: Web Server & Order Execution",
      "tasks": ["15", "16", "17", "18"]
    },
    {
      "name": "Wave 8: Auto-Delivery & Rollback",
      "tasks": ["19", "20", "21"]
    },
    {
      "name": "Wave 9: Voucher & History",
      "tasks": ["22", "26"]
    },
    {
      "name": "Wave 10: Voucher Integration & History UI",
      "tasks": ["23", "24", "27"]
    },
    {
      "name": "Wave 11: Voucher Checkout",
      "tasks": ["25"]
    },
    {
      "name": "Wave 12: Admin Foundation",
      "tasks": ["28"]
    },
    {
      "name": "Wave 13: Admin Access & Handler",
      "tasks": ["29", "30"]
    },
    {
      "name": "Wave 14: Admin Features",
      "tasks": ["31", "32", "33", "34"]
    },
    {
      "name": "Wave 15: Error Handling",
      "tasks": ["35"]
    },
    {
      "name": "Wave 16: Resilience",
      "tasks": ["36", "37"]
    },
    {
      "name": "Wave 17: Deployment",
      "tasks": ["38", "39", "40", "41"]
    }
  ]
}
```

## Notes

- Phases must be executed sequentially (3 → 4 → 5 → 6 → 7 → 8) as each builds on the previous
- Phase 3 is the foundation — all subsequent phases depend on live database connectivity
- Tripay integration (Phase 4) is critical path for both deposits and direct payment orders
- Auto-delivery (Phase 5) depends on both order execution and credential repository being ready
- Admin panel (Phase 7) can be partially developed in parallel with Phase 6 since it uses the same repositories
- Error handling (Phase 8) should be implemented last to wrap all existing functionality
- All SQL mutations (balance, stock) must use atomic guards to prevent race conditions
- Property-based tests should be written alongside each phase's implementation using Hypothesis
