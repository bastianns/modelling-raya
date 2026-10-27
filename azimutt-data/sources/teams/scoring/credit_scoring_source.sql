-- =============================================================================
-- Enterprise Data Modeling: Sumber Skema DDL Statis - Tim Scoring
-- =============================================================================

CREATE TABLE scoring.credit_applications (
    application_id UUID PRIMARY KEY,
    customer_cif VARCHAR(20) NOT NULL,
    requested_amount DECIMAL(18,2) NOT NULL,
    risk_tier VARCHAR(5) NOT NULL,
    score_value INT NOT NULL,
    application_status VARCHAR(20) DEFAULT 'IN_REVIEW',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scoring.scorecard_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_code VARCHAR(50) UNIQUE NOT NULL,
    weight_percentage DECIMAL(5,2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scoring_cif ON scoring.credit_applications(customer_cif);
