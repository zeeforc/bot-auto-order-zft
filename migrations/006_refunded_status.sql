-- Migration 006: Add 'refunded' to allowed order status values.
-- Replaces orders_status_valid CHECK constraint to include 'refunded'.

ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_status_valid;

ALTER TABLE orders
    ADD CONSTRAINT orders_status_valid
    CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled', 'refunded'));
