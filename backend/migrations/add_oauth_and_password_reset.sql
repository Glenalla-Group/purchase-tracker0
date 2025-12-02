-- Migration script to add OAuth support and password reset functionality
-- Database: PostgreSQL
-- Description: Adds OAuth fields to users table and creates password_reset_tokens table

-- Add OAuth fields to users table
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE,
    ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50),
    ALTER COLUMN password DROP NOT NULL;

-- Create indexes on new fields
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);

-- Add comments
COMMENT ON COLUMN users.google_id IS 'Google OAuth unique identifier';
COMMENT ON COLUMN users.oauth_provider IS 'OAuth provider name (google, facebook, etc.)';
COMMENT ON COLUMN users.password IS 'Bcrypt hashed password (nullable for OAuth users)';

-- Create password_reset_tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE password_reset_tokens IS 'Stores tokens for password reset requests';
COMMENT ON COLUMN password_reset_tokens.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN password_reset_tokens.user_id IS 'Foreign key reference to users table';
COMMENT ON COLUMN password_reset_tokens.token IS 'Unique token for password reset (UUID)';
COMMENT ON COLUMN password_reset_tokens.expires_at IS 'When this token expires (typically 1 hour from creation)';
COMMENT ON COLUMN password_reset_tokens.used IS 'Whether this token has been used';
COMMENT ON COLUMN password_reset_tokens.created_at IS 'When this token was created';

-- Create indexes for password_reset_tokens table
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);

