-- =====================================================================
-- Migration 004: Account display template per product
-- 
-- Setiap produk bisa punya template tampilan akun yang berbeda.
-- Contoh Netflix: "Email|Password|Profile|PIN"
-- Contoh Canva: "Email|Password"
-- =====================================================================

ALTER TABLE products ADD COLUMN IF NOT EXISTS account_template TEXT;

-- Set default templates for common products
-- Format: label1|label2|label3|...
-- Saat deliver, bot akan match label dengan data akun per field
COMMENT ON COLUMN products.account_template IS 'Display template for account data. Format: Label1|Label2|Label3. Matched positionally with account_data fields separated by |';
