-- Database initialization for DTEK power outage monitoring bot

-- Drop old tables to recreate with correct schema
-- CASCADE automatically drops dependent objects (foreign keys, indexes, etc.)
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS outages CASCADE;
DROP TABLE IF EXISTS addresses CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users(chat_id);

-- Addresses table (with queue_number in main CREATE TABLE)
CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    region VARCHAR(50) NOT NULL,
    city VARCHAR(255),
    street VARCHAR(255) NOT NULL,
    building VARCHAR(50),
    full_address TEXT NOT NULL,
    normalized_address TEXT,
    queue_number VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_addresses_user_id ON addresses(user_id);
CREATE INDEX IF NOT EXISTS idx_addresses_region ON addresses(region);
CREATE INDEX IF NOT EXISTS idx_addresses_normalized ON addresses(normalized_address);

-- Outages table
CREATE TABLE IF NOT EXISTS outages (
    id SERIAL PRIMARY KEY,
    region VARCHAR(50) NOT NULL,
    outage_type VARCHAR(50) NOT NULL,
    affected_area TEXT NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    description TEXT,
    source_url TEXT,
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outages_region ON outages(region);
CREATE INDEX IF NOT EXISTS idx_outages_created_at ON outages(created_at);
CREATE INDEX IF NOT EXISTS idx_outages_type ON outages(outage_type);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    outage_id INTEGER REFERENCES outages(id) ON DELETE CASCADE,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'sent'
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_outage_id ON notifications(outage_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_unique ON notifications(user_id, outage_id);
