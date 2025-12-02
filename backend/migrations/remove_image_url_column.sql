-- Migration: Remove image_url column from oa_sourcing table
-- Purpose: The image_url is redundant with unique_id field
--          Image URLs can be constructed from unique_id dynamically
-- Date: 2025-10-21

-- Remove image_url column from oa_sourcing table
ALTER TABLE oa_sourcing DROP COLUMN IF EXISTS image_url;

-- Note: Images are now constructed dynamically using unique_id
-- Example: https://images.footlocker.com/is/image/FLEU/{unique_id}

