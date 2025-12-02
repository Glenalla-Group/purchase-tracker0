-- Migration script to add retailer relationship to oa_sourcing table
-- This script is for EXISTING databases that already have oa_sourcing table
-- Database: AWS PostgreSQL

-- Step 1: Create retailers table if it doesn't exist
CREATE TABLE IF NOT EXISTS retailers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    link TEXT,
    wholesale VARCHAR(10),  -- 'yes', 'no', 'n/a'
    cancel_for_bulk BOOLEAN DEFAULT FALSE,
    location VARCHAR(50),  -- 'EU', 'USA', CANADA', 'AU', 'UK', 'SA'
    shopify BOOLEAN DEFAULT FALSE,
    
    -- Statistics (calculated fields)
    total_spend NUMERIC(12, 2) DEFAULT 0.0,
    total_qty_of_items_ordered INTEGER DEFAULT 0,
    percent_of_cancelled_qty NUMERIC(5, 2) DEFAULT 0.0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Add indexes for retailers if they don't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_retailers_name') THEN
        CREATE INDEX idx_retailers_name ON retailers(name);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_retailers_location') THEN
        CREATE INDEX idx_retailers_location ON retailers(location);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_retailers_wholesale') THEN
        CREATE INDEX idx_retailers_wholesale ON retailers(wholesale);
    END IF;
END $$;

-- Step 3: Create trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_retailers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 4: Create trigger if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_update_retailers_updated_at') THEN
        CREATE TRIGGER trigger_update_retailers_updated_at
        BEFORE UPDATE ON retailers
        FOR EACH ROW
        EXECUTE FUNCTION update_retailers_updated_at();
    END IF;
END $$;

-- Step 5: Add retailer_id column to oa_sourcing if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'oa_sourcing' AND column_name = 'retailer_id'
    ) THEN
        ALTER TABLE oa_sourcing ADD COLUMN retailer_id INTEGER;
        
        -- Add foreign key constraint
        ALTER TABLE oa_sourcing 
        ADD CONSTRAINT fk_oa_sourcing_retailer 
        FOREIGN KEY (retailer_id) REFERENCES retailers(id);
        
        -- Add index
        CREATE INDEX idx_oa_sourcing_retailer_id ON oa_sourcing(retailer_id);
        
        -- Add comment
        COMMENT ON COLUMN oa_sourcing.retailer_id IS 'Foreign key reference to retailers table';
        
        RAISE NOTICE 'Added retailer_id column to oa_sourcing table';
    ELSE
        RAISE NOTICE 'retailer_id column already exists in oa_sourcing table';
    END IF;
END $$;

-- Step 6: Populate retailers table from existing retailer_name data (if column exists)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'oa_sourcing' AND column_name = 'retailer_name'
    ) THEN
        INSERT INTO retailers (name)
        SELECT DISTINCT retailer_name
        FROM oa_sourcing
        WHERE retailer_name IS NOT NULL 
          AND retailer_name != ''
          AND NOT EXISTS (
            SELECT 1 FROM retailers WHERE name = oa_sourcing.retailer_name
          )
        ORDER BY retailer_name;
        
        RAISE NOTICE 'Populated retailers from retailer_name data';
    ELSE
        RAISE NOTICE 'retailer_name column does not exist, skipping population';
    END IF;
END $$;

-- Step 7: Update retailer_id in oa_sourcing based on retailer_name (if column exists)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'oa_sourcing' AND column_name = 'retailer_name'
    ) THEN
        UPDATE oa_sourcing
        SET retailer_id = retailers.id
        FROM retailers
        WHERE oa_sourcing.retailer_name = retailers.name
          AND oa_sourcing.retailer_id IS NULL;
        
        RAISE NOTICE 'Linked oa_sourcing records to retailers';
    END IF;
END $$;

-- Step 8: Drop retailer_name column (now redundant)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'oa_sourcing' AND column_name = 'retailer_name'
    ) THEN
        ALTER TABLE oa_sourcing DROP COLUMN retailer_name;
        RAISE NOTICE 'Dropped retailer_name column (now using retailer_id)';
    ELSE
        RAISE NOTICE 'retailer_name column already removed';
    END IF;
END $$;

-- Display summary
DO $$ 
DECLARE
    total_retailers INTEGER;
    total_oa_sourcing INTEGER;
    linked_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_retailers FROM retailers;
    SELECT COUNT(*) INTO total_oa_sourcing FROM oa_sourcing;
    SELECT COUNT(*) INTO linked_count FROM oa_sourcing WHERE retailer_id IS NOT NULL;
    
    RAISE NOTICE '=====================================';
    RAISE NOTICE 'MIGRATION COMPLETE!';
    RAISE NOTICE '=====================================';
    RAISE NOTICE 'Total retailers: %', total_retailers;
    RAISE NOTICE 'Total OA sourcing records: %', total_oa_sourcing;
    RAISE NOTICE 'Linked records: %', linked_count;
    RAISE NOTICE 'Unlinked records: %', total_oa_sourcing - linked_count;
    RAISE NOTICE '=====================================';
END $$;

-- Display any OA sourcing records that couldn't be linked
SELECT 
    id, 
    lead_id,
    'No retailer linked' as issue
FROM oa_sourcing
WHERE retailer_id IS NULL
ORDER BY id;

