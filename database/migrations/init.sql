-- Ініціалізація бази даних для бота моніторингу відключень ДТЕК

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    region VARCHAR(50) NOT NULL,
    city VARCHAR(255),
    street VARCHAR(255) NOT NULL,
    building VARCHAR(50),
    full_address TEXT NOT NULL,
    normalized_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_addresses_user_id ON addresses(user_id);
CREATE INDEX IF NOT EXISTS idx_addresses_region ON addresses(region);
CREATE INDEX IF NOT EXISTS idx_addresses_normalized ON addresses(normalized_address);

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

-- Додати поле для номера черги
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='addresses' AND column_name='queue_number') THEN
        ALTER TABLE addresses ADD COLUMN queue_number VARCHAR(20);
    END IF;
END $$;
