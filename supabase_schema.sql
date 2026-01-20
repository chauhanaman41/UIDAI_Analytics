-- Enable UUID extension if needed (though we use BIGSERIAL here, standard for analytics)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Enrollments Table
CREATE TABLE IF NOT EXISTS enrollments (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    state VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    pincode VARCHAR(6),
    age_0_5 INTEGER CHECK (age_0_5 >= 0),
    age_5_17 INTEGER CHECK (age_5_17 >= 0),
    age_18_greater INTEGER CHECK (age_18_greater >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for Enrollments
CREATE INDEX IF NOT EXISTS idx_enrollments_date ON enrollments(date);
CREATE INDEX IF NOT EXISTS idx_enrollments_state_district ON enrollments(state, district);

-- 2. Biometric Attempts Table
CREATE TABLE IF NOT EXISTS biometric_attempts (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    state VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    pincode VARCHAR(6),
    bio_age_5_17 INTEGER CHECK (bio_age_5_17 >= 0),
    bio_age_17_ INTEGER CHECK (bio_age_17_ >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for Biometric Attempts
CREATE INDEX IF NOT EXISTS idx_biometric_date ON biometric_attempts(date);
CREATE INDEX IF NOT EXISTS idx_biometric_state_district ON biometric_attempts(state, district);

-- 3. Demographic Updates Table
CREATE TABLE IF NOT EXISTS demographic_updates (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    state VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    pincode VARCHAR(6),
    demo_age_5_17 INTEGER CHECK (demo_age_5_17 >= 0),
    demo_age_17_ INTEGER CHECK (demo_age_17_ >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for Demographic Updates
CREATE INDEX IF NOT EXISTS idx_demographic_date ON demographic_updates(date);
CREATE INDEX IF NOT EXISTS idx_demographic_state_district ON demographic_updates(state, district);

-- 4. Anomaly Alerts Table [NEW]
CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    state VARCHAR(100),
    district VARCHAR(100),
    metric_name VARCHAR(100) NOT NULL,
    anomaly_value FLOAT NOT NULL,
    severity_score FLOAT,
    anomaly_type VARCHAR(50), -- 'spike', 'drop', 'irregular'
    detection_methods TEXT[], -- Array of methods that flagged it e.g. ['z_score', 'iqr']
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_date ON anomaly_alerts(date);
CREATE INDEX IF NOT EXISTS idx_anomaly_location ON anomaly_alerts(state, district);
