-- Migration: Add created_at column to asin_bank table
-- Date: 2025-11-12
-- Description: Adds a created_at timestamp column to track when ASINs were added

-- Add created_at column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'asin_bank' 
        AND column_name = 'created_at'
    ) THEN
        ALTER TABLE asin_bank 
        ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL;
        
        -- Add comment for the new column
        COMMENT ON COLUMN asin_bank.created_at IS 'Timestamp when the ASIN was added to the bank';
        
        RAISE NOTICE 'Column created_at added to asin_bank table';
    ELSE
        RAISE NOTICE 'Column created_at already exists in asin_bank table';
    END IF;
END $$;

