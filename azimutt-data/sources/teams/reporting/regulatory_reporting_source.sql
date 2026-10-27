-- =============================================================================
-- Enterprise Data Modeling: Sumber Skema DDL Statis - Tim Pelaporan Regulasi
-- =============================================================================

CREATE TABLE reporting.monthly_loan_reports (
    report_id BIGSERIAL PRIMARY KEY,
    period_yyyymm VARCHAR(6) NOT NULL,
    account_number VARCHAR(30) NOT NULL,
    collectibility_status CHAR(1) NOT NULL,
    outstanding_balance DECIMAL(18,2) NOT NULL,
    provision_amount DECIMAL(18,2) NOT NULL,
    submission_status VARCHAR(20) DEFAULT 'PENDING_APPROVAL',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reporting.regulator_submissions (
    submission_id UUID PRIMARY KEY,
    report_code VARCHAR(20) NOT NULL,
    submission_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    acknowledgment_receipt VARCHAR(100),
    notes TEXT
);

CREATE INDEX idx_reporting_period ON reporting.monthly_loan_reports(period_yyyymm);
