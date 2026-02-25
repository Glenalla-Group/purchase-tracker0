-- Migration: Change purchase_tracker.date from DATE to TIMESTAMP
-- Date: 2025-02-14
-- Description: Store purchase date and time for accurate display. Existing date-only
--   values become timestamp at midnight (00:00:00) when cast.

-- PostgreSQL: Alter column type (DATE -> TIMESTAMP). Existing dates become midnight.
ALTER TABLE purchase_tracker 
  ALTER COLUMN date TYPE TIMESTAMP 
  USING date::timestamp;

COMMENT ON COLUMN purchase_tracker.date IS 'Purchase date and time (when the order was placed)';
