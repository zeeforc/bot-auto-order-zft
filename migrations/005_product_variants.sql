-- =====================================================================
-- Migration 005: Product Variants
--
-- Produk induk = kategori besar (CANVA, NETFLIX, SPOTIFY, dll)
-- Variant = sub-produk spesifik (Canva Pro 1 Bulan, Netflix 1 Bulan, dll)
--
-- Flow: User pilih produk induk → lihat variasi → pilih variasi → order
-- Account stock di-assign ke variant_id (bukan product_id)
-- =====================================================================

CREATE TABLE IF NOT EXISTS product_variants (
    id            BIGSERIAL    PRIMARY KEY,
    product_id    BIGINT       NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name          VARCHAR(128) NOT NULL,          -- Nama variasi (e.g. "Canva Pro 1 Bulan")
    code          VARCHAR(32),                    -- Kode unik variasi (e.g. "cp1b")
    description   TEXT,                           -- Deskripsi khusus variasi
    price         BIGINT       NOT NULL DEFAULT 0
                                CONSTRAINT variants_price_non_negative CHECK (price >= 0),
    stock         INTEGER      NOT NULL DEFAULT 0
                                CONSTRAINT variants_stock_non_negative CHECK (stock >= 0),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    account_template TEXT,                        -- Template akun khusus variasi (override product)
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_variants_product_id ON product_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_variants_active ON product_variants(product_id) WHERE is_active = TRUE;

-- Add variant_id to account_stock (optional, for variant-level stock)
ALTER TABLE account_stock ADD COLUMN IF NOT EXISTS variant_id BIGINT REFERENCES product_variants(id);
CREATE INDEX IF NOT EXISTS idx_account_stock_variant ON account_stock(variant_id) WHERE is_used = FALSE;

-- Add variant_id to orders (track which variant was ordered)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS variant_id BIGINT REFERENCES product_variants(id);

-- Add short_description to products (for the overview display)
ALTER TABLE products ADD COLUMN IF NOT EXISTS short_description TEXT;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS variants_set_updated_at ON product_variants;
CREATE TRIGGER variants_set_updated_at
    BEFORE UPDATE ON product_variants
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();
