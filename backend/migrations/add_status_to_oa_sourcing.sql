-- Migration: Add status field to oa_sourcing table
-- Date: 2026-01-13
-- Description: Add a status column to track whether a lead is 'draft' or 'complete'

ALTER TABLE oa_sourcing ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';

-- Update existing records to have 'draft' status
UPDATE oa_sourcing SET status = 'draft' WHERE status IS NULL;

-- Add a comment to the column
COMMENT ON COLUMN oa_sourcing.status IS 'Lead status: draft or complete';
