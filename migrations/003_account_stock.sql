-- =====================================================================
-- Migration 003: Account Stock (data akun per produk)
-- 
-- Setiap produk punya pool akun (email:password atau data lainnya).
-- Saat order paid, ambil 1 akun dari pool → kirim ke user → mark used.
-- =====================================================================

CREATE TABLE IF NOT EXISTS account_stock (
    id            BIGSERIAL    PRIMARY KEY,
    product_id    BIGINT       NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    account_data  TEXT         NOT NULL,          -- email:password atau data akun lainnya
    is_used       BOOLEAN      NOT NULL DEFAULT FALSE,
    used_by       BIGINT       REFERENCES users(telegram_id),  -- user yang pakai akun ini
    order_id      VARCHAR(64)  REFERENCES orders(id),          -- order yang pakai akun ini
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    used_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_account_stock_product_available
    ON account_stock(product_id)
    WHERE is_used = FALSE;

CREATE INDEX IF NOT EXISTS idx_account_stock_order
    ON account_stock(order_id);
