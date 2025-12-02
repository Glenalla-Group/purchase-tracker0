-- Migration: Remove redundant datetime columns from oa_sourcing table
-- Purpose: Remove month, day, year, hh, mm, ss columns since we already have timestamp column
-- Date: 2025-10-21

-- Remove redundant datetime component columns from oa_sourcing table
ALTER TABLE oa_sourcing DROP COLUMN IF EXISTS month;
ALTER TABLE oa_sourcing DROP COLUMN IF EXISTS day;
ALTER TABLE oa_sourcing DROP COLUMN IF EXISTS year;
ALTER TABLE oa_sourcing DROP COLUMN IF EXISTS hh;
ALTER TABLE oa_sourcing DROP COLUMN IF EXISTS mm;
ALTER TABLE oa_sourcing DROP COLUMN IF EXISTS ss;

-- Note: The 'timestamp' column is sufficient for all datetime needs
COMMENT ON COLUMN oa_sourcing.timestamp IS 'Complete date and time when lead was submitted - replaces individual month/day/year/hh/mm/ss columns';

