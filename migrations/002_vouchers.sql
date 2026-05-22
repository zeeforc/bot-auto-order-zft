-- =====================================================================
-- Migration 002: Voucher System
-- =====================================================================

CREATE TABLE IF NOT EXISTS vouchers (
    id            BIGSERIAL    PRIMARY KEY,
    code          VARCHAR(32)  NOT NULL UNIQUE,
    discount_type VARCHAR(16)  NOT NULL DEFAULT 'fixed'
                                CONSTRAINT vouchers_type_valid CHECK (discount_type IN ('fixed', 'percent')),
    discount_value BIGINT      NOT NULL
                                CONSTRAINT vouchers_value_positive CHECK (discount_value > 0),
    min_purchase  BIGINT       NOT NULL DEFAULT 0,
    max_discount  BIGINT,                                          -- NULL = unlimited (untuk percent type)
    max_usage     INTEGER      NOT NULL DEFAULT 1,                 -- Total usage allowed
    used_count    INTEGER      NOT NULL DEFAULT 0,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    expired_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vouchers_code ON vouchers(code);

DROP TRIGGER IF EXISTS vouchers_set_updated_at ON vouchers;
CREATE TRIGGER vouchers_set_updated_at
    BEFORE UPDATE ON vouchers
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

-- Track siapa yang sudah pakai voucher (prevent double use per user)
CREATE TABLE IF NOT EXISTS voucher_usages (
    id            BIGSERIAL    PRIMARY KEY,
    voucher_id    BIGINT       NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    user_id       BIGINT       NOT NULL,
    order_id      VARCHAR(64),
    used_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(voucher_id, user_id)                                    -- 1 voucher per user
);

CREATE INDEX IF NOT EXISTS idx_voucher_usages_user ON voucher_usages(user_id);
