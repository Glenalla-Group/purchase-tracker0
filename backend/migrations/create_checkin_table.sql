-- Migration script to create checkin table
-- Database: AWS PostgreSQL

-- Create checkin table
CREATE TABLE IF NOT EXISTS checkin (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(200),
    item_name VARCHAR(500),
    asin_bank_id INTEGER REFERENCES asin_bank(id) ON DELETE SET NULL,
    quantity INTEGER NOT NULL,
    checked_in_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE checkin IS 'Tracks items checked in at warehouse/fulfillment center';
COMMENT ON COLUMN checkin.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN checkin.order_number IS 'Order number for tracking';
COMMENT ON COLUMN checkin.item_name IS 'Product/item name';
COMMENT ON COLUMN checkin.asin_bank_id IS 'Foreign key reference to asin_bank (for ASIN and size)';
COMMENT ON COLUMN checkin.quantity IS 'Number of items checked in';
COMMENT ON COLUMN checkin.checked_in_at IS 'Date and time of check-in';

-- Indexes for checkin table
CREATE INDEX IF NOT EXISTS idx_checkin_order_number ON checkin(order_number);
CREATE INDEX IF NOT EXISTS idx_checkin_asin_bank_id ON checkin(asin_bank_id);
CREATE INDEX IF NOT EXISTS idx_checkin_checked_in_at ON checkin(checked_in_at);



