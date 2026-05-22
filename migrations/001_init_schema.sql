-- =====================================================================
-- Migration 001: Initial Schema (users, products, orders)
-- Target  : PostgreSQL 14+ / Supabase
-- Author  : T-Store Auto Order Bot - Phase 2 (Database Integration)
--
-- Catatan:
-- 1. Semua nilai uang (balance, price, total_price) disimpan sebagai BIGINT
--    dalam satuan IDR (Rupiah) tanpa desimal. Hindari FLOAT/REAL untuk uang
--    karena akan membuat error pembulatan.
-- 2. Constraint `stock >= 0` dan `balance >= 0` ditegakkan di level DB
--    sebagai garis pertahanan terakhir terhadap overselling / saldo minus.
-- 3. Atomic update untuk pemotongan stok/saldo wajib dilakukan via single
--    `UPDATE ... WHERE stock >= qty` (lihat ProductRepository.decrement_stock).
-- =====================================================================

-- ---------------------------------------------------------------------
-- Trigger helper: auto update kolom `updated_at`
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- Table: users
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    telegram_id   BIGINT       PRIMARY KEY,                         -- Telegram user ID (bisa > INT32)
    username      VARCHAR(64),
    first_name    VARCHAR(128),
    last_name     VARCHAR(128),
    phone         VARCHAR(32),
    balance       BIGINT       NOT NULL DEFAULT 0
                                CONSTRAINT users_balance_non_negative CHECK (balance >= 0),
    is_banned     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

DROP TRIGGER IF EXISTS users_set_updated_at ON users;
CREATE TRIGGER users_set_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

-- ---------------------------------------------------------------------
-- Table: products
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id            BIGSERIAL    PRIMARY KEY,
    name          VARCHAR(128) NOT NULL,
    description   TEXT,
    category      VARCHAR(64),
    price         BIGINT       NOT NULL
                                CONSTRAINT products_price_non_negative CHECK (price >= 0),
    stock         INTEGER      NOT NULL DEFAULT 0
                                CONSTRAINT products_stock_non_negative CHECK (stock >= 0),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Partial index: bantu filter daftar produk yang masih dijual.
CREATE INDEX IF NOT EXISTS idx_products_active
    ON products(id)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

DROP TRIGGER IF EXISTS products_set_updated_at ON products;
CREATE TRIGGER products_set_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

-- ---------------------------------------------------------------------
-- Table: orders
-- Catatan: order_id di-generate sebagai UUID atau nanoid di aplikasi,
-- bukan auto-increment. Ini lebih aman untuk distributed system.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id                VARCHAR(64)  PRIMARY KEY,                     -- UUID (36 chars)
    user_id           BIGINT       NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    product_id        BIGINT       NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity          INTEGER      NOT NULL
                                    CONSTRAINT orders_qty_positive CHECK (quantity > 0),
    total_price       BIGINT       NOT NULL
                                    CONSTRAINT orders_price_non_negative CHECK (total_price >= 0),
    status            VARCHAR(32)  NOT NULL DEFAULT 'pending'
                                    CONSTRAINT orders_status_valid CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled')),
    payment_method    VARCHAR(32),                                  -- saldo, qris, va, etc
    payment_ref       VARCHAR(128),                                 -- Reference dari payment gateway
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

DROP TRIGGER IF EXISTS orders_set_updated_at ON orders;
CREATE TRIGGER orders_set_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

