-- Migration script to create PTO Requests and Holidays tables
-- Database: AWS PostgreSQL

-- Create pto_requests table
CREATE TABLE IF NOT EXISTS pto_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days NUMERIC(5, 2) NOT NULL,
    request_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    reason TEXT,
    notes TEXT,
    approved_by_id INTEGER,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT fk_pto_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_pto_approved_by FOREIGN KEY (approved_by_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_pto_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_pto_status CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    CONSTRAINT chk_pto_type CHECK (request_type IN ('pto', 'sick', 'personal', 'holiday'))
);

COMMENT ON TABLE pto_requests IS 'Stores employee PTO (Paid Time Off) requests';
COMMENT ON COLUMN pto_requests.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN pto_requests.user_id IS 'Foreign key to users table';
COMMENT ON COLUMN pto_requests.start_date IS 'Start date of PTO request';
COMMENT ON COLUMN pto_requests.end_date IS 'End date of PTO request';
COMMENT ON COLUMN pto_requests.total_days IS 'Total days requested (can be partial, e.g., 0.5)';
COMMENT ON COLUMN pto_requests.request_type IS 'Type of request: pto, sick, personal, holiday';
COMMENT ON COLUMN pto_requests.status IS 'Request status: pending, approved, rejected, cancelled';
COMMENT ON COLUMN pto_requests.reason IS 'Reason for the PTO request';
COMMENT ON COLUMN pto_requests.notes IS 'Additional notes';
COMMENT ON COLUMN pto_requests.approved_by_id IS 'User ID who approved the request';
COMMENT ON COLUMN pto_requests.approved_at IS 'Timestamp when request was approved';

-- Create indexes for pto_requests
CREATE INDEX idx_pto_user_id ON pto_requests(user_id);
CREATE INDEX idx_pto_start_date ON pto_requests(start_date);
CREATE INDEX idx_pto_end_date ON pto_requests(end_date);
CREATE INDEX idx_pto_status ON pto_requests(status);
CREATE INDEX idx_pto_dates_range ON pto_requests USING GIST (daterange(start_date, end_date, '[]'));

-- Create holidays table
CREATE TABLE IF NOT EXISTS holidays (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    date DATE NOT NULL,
    country VARCHAR(50) NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE NOT NULL,
    year INTEGER,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT chk_holiday_recurring CHECK (
        (is_recurring = TRUE AND year IS NULL) OR 
        (is_recurring = FALSE AND year IS NOT NULL)
    )
);

COMMENT ON TABLE holidays IS 'Stores company holidays (US, PH, etc.)';
COMMENT ON COLUMN holidays.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN holidays.name IS 'Name of the holiday';
COMMENT ON COLUMN holidays.date IS 'Date of the holiday';
COMMENT ON COLUMN holidays.country IS 'Country code: US, PH, BOTH, etc.';
COMMENT ON COLUMN holidays.is_recurring IS 'Whether the holiday recurs yearly';
COMMENT ON COLUMN holidays.year IS 'Specific year if not recurring, NULL if recurring';
COMMENT ON COLUMN holidays.description IS 'Description of the holiday';

-- Create indexes for holidays
CREATE INDEX idx_holidays_date ON holidays(date);
CREATE INDEX idx_holidays_country ON holidays(country);
CREATE INDEX idx_holidays_year ON holidays(year);
CREATE INDEX idx_holidays_recurring ON holidays(is_recurring);

-- Create a function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to automatically update updated_at
CREATE TRIGGER update_pto_requests_updated_at
    BEFORE UPDATE ON pto_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_holidays_updated_at
    BEFORE UPDATE ON holidays
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert some common US holidays (recurring)
INSERT INTO holidays (name, date, country, is_recurring, description) VALUES
    ('New Year''s Day', '2024-01-01', 'US', TRUE, 'New Year''s Day'),
    ('Martin Luther King Jr. Day', '2024-01-15', 'US', TRUE, 'Third Monday in January'),
    ('Presidents Day', '2024-02-19', 'US', TRUE, 'Third Monday in February'),
    ('Memorial Day', '2024-05-27', 'US', TRUE, 'Last Monday in May'),
    ('Independence Day', '2024-07-04', 'US', TRUE, 'Independence Day'),
    ('Labor Day', '2024-09-02', 'US', TRUE, 'First Monday in September'),
    ('Columbus Day', '2024-10-14', 'US', TRUE, 'Second Monday in October'),
    ('Veterans Day', '2024-11-11', 'US', TRUE, 'Veterans Day'),
    ('Thanksgiving', '2024-11-28', 'US', TRUE, 'Fourth Thursday in November'),
    ('Christmas Day', '2024-12-25', 'US', TRUE, 'Christmas Day')
ON CONFLICT DO NOTHING;

-- Insert some common Philippines holidays (recurring)
INSERT INTO holidays (name, date, country, is_recurring, description) VALUES
    ('New Year''s Day', '2024-01-01', 'PH', TRUE, 'New Year''s Day'),
    ('People Power Revolution', '2024-02-25', 'PH', TRUE, 'People Power Revolution Anniversary'),
    ('Araw ng Kagitingan', '2024-04-09', 'PH', TRUE, 'Day of Valor'),
    ('Labor Day', '2024-05-01', 'PH', TRUE, 'Labor Day'),
    ('Independence Day', '2024-06-12', 'PH', TRUE, 'Philippine Independence Day'),
    ('National Heroes Day', '2024-08-26', 'PH', TRUE, 'Last Monday of August'),
    ('Bonifacio Day', '2024-11-30', 'PH', TRUE, 'Bonifacio Day'),
    ('Rizal Day', '2024-12-30', 'PH', TRUE, 'Rizal Day'),
    ('Christmas Day', '2024-12-25', 'PH', TRUE, 'Christmas Day')
ON CONFLICT DO NOTHING;

