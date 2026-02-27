-- Create email_manual_review table for items needing manual data entry
-- Used when retailer emails (e.g. Revolve cancellation) lack order_number or unique_id
-- Run after create_tables.sql

CREATE TABLE IF NOT EXISTS email_manual_review (
    id SERIAL PRIMARY KEY,
    gmail_message_id VARCHAR(100) NOT NULL UNIQUE,
    retailer VARCHAR(50) NOT NULL,
    email_type VARCHAR(50) NOT NULL,
    subject TEXT,
    
    -- Partial extracted data (JSON for flexibility)
    extracted_order_number VARCHAR(200),
    extracted_items JSONB,
    missing_fields VARCHAR(200),
    error_reason TEXT,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_manual_review_status ON email_manual_review(status);
CREATE INDEX IF NOT EXISTS idx_email_manual_review_retailer ON email_manual_review(retailer);
CREATE INDEX IF NOT EXISTS idx_email_manual_review_created_at ON email_manual_review(created_at DESC);

COMMENT ON TABLE email_manual_review IS 'Emails needing manual review (e.g. Revolve cancellation with missing order_number or unique_id)';
