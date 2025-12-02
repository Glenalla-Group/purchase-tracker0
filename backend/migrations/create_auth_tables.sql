-- Migration script to create authentication tables
-- Database: PostgreSQL
-- Description: Creates user_roles and users tables for authentication

-- Drop tables if they exist (users first due to foreign key)
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS user_roles CASCADE;

-- Create user_roles table
CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(200),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_roles IS 'Stores available user roles (admin, user, etc.)';
COMMENT ON COLUMN user_roles.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN user_roles.name IS 'Role name (unique): admin, user, manager, etc.';
COMMENT ON COLUMN user_roles.description IS 'Description of the role and its permissions';
COMMENT ON COLUMN user_roles.created_at IS 'When this role was created';

-- Create index on role name
CREATE INDEX idx_user_roles_name ON user_roles(name);

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES user_roles(id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

COMMENT ON TABLE users IS 'Stores user accounts for authentication';
COMMENT ON COLUMN users.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN users.username IS 'Username / Full name (unique)';
COMMENT ON COLUMN users.email IS 'User email address (unique)';
COMMENT ON COLUMN users.password IS 'Bcrypt hashed password';
COMMENT ON COLUMN users.role_id IS 'Foreign key reference to user_roles table';
COMMENT ON COLUMN users.is_active IS 'Whether the user account is active';
COMMENT ON COLUMN users.created_at IS 'When the user account was created';
COMMENT ON COLUMN users.updated_at IS 'When the user account was last updated';
COMMENT ON COLUMN users.last_login IS 'When the user last logged in';

-- Create indexes for users table
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update updated_at
CREATE TRIGGER trigger_update_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_users_updated_at();

-- Insert default roles
INSERT INTO user_roles (name, description) VALUES
    ('admin', 'Administrator with full access to all features'),
    ('user', 'Regular user with limited access');

-- Note: Default admin user should be created using the seed script or API
-- Password: demo1234 (will be hashed by the application)

COMMENT ON TABLE user_roles IS 'Default roles: admin (full access), user (limited access)';


