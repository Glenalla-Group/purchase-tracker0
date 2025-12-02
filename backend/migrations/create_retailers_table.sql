-- Migration script to create retailers table
-- Database: AWS PostgreSQL

-- Create retailers table
CREATE TABLE IF NOT EXISTS retailers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    link TEXT,
    wholesale VARCHAR(10),  -- 'yes', 'no', 'n/a'
    cancel_for_bulk BOOLEAN DEFAULT FALSE,
    location VARCHAR(50),  -- 'EU', 'USA', 'CANADA', 'AU', 'UK', 'SA'
    shopify BOOLEAN DEFAULT FALSE,
    
    -- Statistics (calculated fields)
    total_spend NUMERIC(12, 2) DEFAULT 0.0,
    total_qty_of_items_ordered INTEGER DEFAULT 0,
    percent_of_cancelled_qty NUMERIC(5, 2) DEFAULT 0.0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE retailers IS 'Stores retailer information and statistics';
COMMENT ON COLUMN retailers.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN retailers.name IS 'Retailer name (unique)';
COMMENT ON COLUMN retailers.link IS 'Retailer website URL';
COMMENT ON COLUMN retailers.wholesale IS 'Wholesale availability: yes, no, or n/a';
COMMENT ON COLUMN retailers.cancel_for_bulk IS 'Whether retailer cancels bulk orders';
COMMENT ON COLUMN retailers.location IS 'Retailer region: EU, USA, CANADA, AU, UK, SA';
COMMENT ON COLUMN retailers.shopify IS 'Whether retailer uses Shopify';
COMMENT ON COLUMN retailers.total_spend IS 'Total amount spent with this retailer';
COMMENT ON COLUMN retailers.total_qty_of_items_ordered IS 'Total quantity of items ordered from this retailer';
COMMENT ON COLUMN retailers.percent_of_cancelled_qty IS 'Percentage of cancelled quantity';

-- Indexes for retailers (PostgreSQL syntax)
CREATE INDEX IF NOT EXISTS idx_retailers_name ON retailers(name);
CREATE INDEX IF NOT EXISTS idx_retailers_location ON retailers(location);
CREATE INDEX IF NOT EXISTS idx_retailers_wholesale ON retailers(wholesale);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_retailers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update updated_at
CREATE TRIGGER trigger_update_retailers_updated_at
BEFORE UPDATE ON retailers
FOR EACH ROW
EXECUTE FUNCTION update_retailers_updated_at();

