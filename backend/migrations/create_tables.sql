-- Migration script to create purchase tracker database tables
-- Database: AWS PostgreSQL

-- Drop tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS purchase_tracker CASCADE;
DROP TABLE IF EXISTS oa_sourcing CASCADE;
DROP TABLE IF EXISTS asin_bank CASCADE;
DROP TABLE IF EXISTS retailers CASCADE;
DROP TABLE IF EXISTS checkin CASCADE;

-- Create retailers table FIRST (since oa_sourcing will reference it)
CREATE TABLE retailers (
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
CREATE INDEX idx_retailers_name ON retailers(name);
CREATE INDEX idx_retailers_location ON retailers(location);
CREATE INDEX idx_retailers_wholesale ON retailers(wholesale);

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

-- Create asin_bank table
CREATE TABLE asin_bank (
    id SERIAL PRIMARY KEY,
    lead_id VARCHAR(100) NOT NULL,
    size VARCHAR(50),
    asin VARCHAR(100) NOT NULL
);

COMMENT ON TABLE asin_bank IS 'Stores all ASINs with their associated lead_id and size';
COMMENT ON COLUMN asin_bank.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN asin_bank.lead_id IS 'Lead ID from OA sourcing sheet';
COMMENT ON COLUMN asin_bank.size IS 'Product size';
COMMENT ON COLUMN asin_bank.asin IS 'Amazon Standard Identification Number';

-- Indexes for asin_bank (PostgreSQL syntax)
CREATE INDEX idx_asin_bank_lead_id ON asin_bank(lead_id);
CREATE INDEX idx_asin_bank_asin ON asin_bank(asin);


-- Create oa_sourcing table
CREATE TABLE oa_sourcing (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    submitted_by VARCHAR(100),
    lead_id VARCHAR(100) NOT NULL UNIQUE,
    
    -- Foreign key to retailers table
    retailer_id INTEGER REFERENCES retailers(id),
    
    product_name_pt_input VARCHAR(500),
    product_name VARCHAR(500),
    product_sku VARCHAR(200),
    retailer_link TEXT,
    amazon_link TEXT,
    unique_id VARCHAR(200),  -- Product unique ID from retailer link (e.g., HJ7395 from FootLocker)
    purchased VARCHAR(50),
    purchase_more_if_available VARCHAR(50),
    pros TEXT,
    cons TEXT,
    other_notes_concerns TEXT,
    head_of_product_review_notes TEXT,
    feedback_and_notes_on_quantity TEXT,
    suggested_total_qty INTEGER,
    pairs_per_lead_id INTEGER,
    pairs_per_sku INTEGER,
    ppu_including_ship NUMERIC(10, 2),
    rsp NUMERIC(10, 2),
    margin NUMERIC(10, 2),
    promo_code VARCHAR(100),
    sales_rank VARCHAR(100),
    
    -- ASIN references (foreign keys to asin_bank)
    asin1_id INTEGER REFERENCES asin_bank(id),
    asin1_recommended_quantity INTEGER,
    
    asin2_id INTEGER REFERENCES asin_bank(id),
    asin2_recommended_quantity INTEGER,
    
    asin3_id INTEGER REFERENCES asin_bank(id),
    asin3_recommended_quantity INTEGER,
    
    asin4_id INTEGER REFERENCES asin_bank(id),
    asin4_recommended_quantity INTEGER,
    
    asin5_id INTEGER REFERENCES asin_bank(id),
    asin5_recommended_quantity INTEGER,
    
    asin6_id INTEGER REFERENCES asin_bank(id),
    asin6_recommended_quantity INTEGER,
    
    asin7_id INTEGER REFERENCES asin_bank(id),
    asin7_recommended_quantity INTEGER,
    
    asin8_id INTEGER REFERENCES asin_bank(id),
    asin8_recommended_quantity INTEGER,
    
    asin9_id INTEGER REFERENCES asin_bank(id),
    asin9_recommended_quantity INTEGER,
    
    asin10_id INTEGER REFERENCES asin_bank(id),
    asin10_recommended_quantity INTEGER,
    
    asin11_id INTEGER REFERENCES asin_bank(id),
    asin11_recommended_quantity INTEGER,
    
    asin12_id INTEGER REFERENCES asin_bank(id),
    asin12_recommended_quantity INTEGER,
    
    asin13_id INTEGER REFERENCES asin_bank(id),
    asin13_recommended_quantity INTEGER,
    
    asin14_id INTEGER REFERENCES asin_bank(id),
    asin14_recommended_quantity INTEGER,
    
    asin15_id INTEGER REFERENCES asin_bank(id),
    asin15_recommended_quantity INTEGER,
    
    -- Additional fields
    asin1_buy_box NUMERIC(10, 2),
    asin1_new_price NUMERIC(10, 2),
    pick_pack_fee NUMERIC(10, 2),
    referral_fee NUMERIC(10, 2),
    total_fee NUMERIC(10, 2),
    margin_using_rsp NUMERIC(10, 2),
    monitored BOOLEAN,
    sourcer VARCHAR(100)
);

COMMENT ON TABLE oa_sourcing IS 'OA Sourcing Lead Submittal data with ASIN references';
COMMENT ON COLUMN oa_sourcing.lead_id IS 'Unique Lead ID';
COMMENT ON COLUMN oa_sourcing.retailer_id IS 'Foreign key reference to retailers table';
COMMENT ON COLUMN oa_sourcing.unique_id IS 'Product unique ID from retailer link (e.g., HJ7395 from FootLocker, HV6417_001 from Finish Line) - used for constructing image URLs';
COMMENT ON COLUMN oa_sourcing.asin1_id IS 'Foreign key reference to asin_bank for ASIN 1';

-- Indexes for oa_sourcing (PostgreSQL syntax)
CREATE INDEX idx_oa_sourcing_lead_id ON oa_sourcing(lead_id);
CREATE INDEX idx_oa_sourcing_retailer_id ON oa_sourcing(retailer_id);
CREATE INDEX idx_oa_sourcing_timestamp ON oa_sourcing(timestamp);
CREATE INDEX idx_oa_sourcing_unique_id ON oa_sourcing(unique_id);


-- Create purchase_tracker table (ULTRA-OPTIMIZED - maximum normalization)
CREATE TABLE purchase_tracker (
    id SERIAL PRIMARY KEY,
    
    -- Foreign keys (required)
    oa_sourcing_id INTEGER NOT NULL REFERENCES oa_sourcing(id),
    asin_bank_id INTEGER REFERENCES asin_bank(id),
    
    -- Denormalized for performance
    lead_id VARCHAR(100),
    
    -- Purchase metadata
    date DATE,
    platform VARCHAR(100),
    order_number VARCHAR(200),
    -- NOTE: supplier removed - same as oa_sourcing.retailer_name
    -- NOTE: unique_id removed - product unique_id belongs in oa_sourcing table
    
    -- Quantities
    og_qty INTEGER,
    final_qty INTEGER,
    
    -- Pricing (if different from planned - otherwise use oa_sourcing.ppu/rsp)
    rsp NUMERIC(10, 2),  -- Actual selling price if different from planned
    -- NOTE: ppu removed - get from oa_sourcing.ppu_including_ship
    -- NOTE: asin, size removed - get from asin_bank via asin_bank_id
    
    -- Fulfillment tracking
    -- NOTE: These are NUMBERS (like 1, 2, 3) indicating stages, NOT dates
    address TEXT,
    shipped_to_pw INTEGER,  -- Number indicating stage/status (e.g., 1, 2, 3)
    arrived INTEGER,         -- Number indicating stage/status
    checked_in INTEGER,      -- Number indicating stage/status
    shipped_out INTEGER,     -- Number indicating stage/status
    delivery_date DATE,      -- Actual date field
    status VARCHAR(100),
    location VARCHAR(200),
    in_bound BOOLEAN,
    tracking VARCHAR(200),
    
    -- FBA fields
    outbound_name VARCHAR(500),
    fba_shipment VARCHAR(200),
    fba_msku VARCHAR(200),
    concat VARCHAR(500),
    audited BOOLEAN DEFAULT FALSE,
    
    -- Refund tracking
    cancelled_qty INTEGER,
    amt_of_cancelled_qty_credit_card NUMERIC(10, 2),
    amt_of_cancelled_qty_gift_card NUMERIC(10, 2),
    expected_refund_amount NUMERIC(10, 2),
    amount_refunded NUMERIC(10, 2),
    refund_status VARCHAR(100),
    refund_method VARCHAR(100),
    date_of_refund DATE,
    
    -- Misc
    notes TEXT,
    validation_bank VARCHAR(200)
);

COMMENT ON TABLE purchase_tracker IS 'Tracks individual purchases with reference to OA sourcing';
COMMENT ON COLUMN purchase_tracker.oa_sourcing_id IS 'Foreign key reference to oa_sourcing table';
COMMENT ON COLUMN purchase_tracker.lead_id IS 'Lead ID for linking to OA sourcing (denormalized for quick lookup)';
COMMENT ON COLUMN purchase_tracker.asin_bank_id IS 'Foreign key reference to asin_bank for ASIN/size data';

-- Indexes for purchase_tracker (PostgreSQL syntax)
CREATE INDEX idx_purchase_tracker_lead_id ON purchase_tracker(lead_id);
CREATE INDEX idx_purchase_tracker_oa_sourcing_id ON purchase_tracker(oa_sourcing_id);
CREATE INDEX idx_purchase_tracker_asin_bank_id ON purchase_tracker(asin_bank_id);
CREATE INDEX idx_purchase_tracker_date ON purchase_tracker(date);


-- Create checkin table
CREATE TABLE checkin (
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
CREATE INDEX idx_checkin_order_number ON checkin(order_number);
CREATE INDEX idx_checkin_asin_bank_id ON checkin(asin_bank_id);
CREATE INDEX idx_checkin_checked_in_at ON checkin(checked_in_at);

