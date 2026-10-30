-- ==============================================================================
-- Bank Raya DAMA-DMBOK Data Architecture
-- Platform: PostgreSQL 16 (OLTP - Core Risk & Credit Scoring Engine)
-- Schema: scoring
-- Security: Zero-Credential-Exposure Static DDL
-- ==============================================================================

CREATE SCHEMA IF NOT EXISTS scoring;

-- Master Aturan Penilaian Scorecard
CREATE TABLE scoring.scorecard_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_code VARCHAR(50) UNIQUE NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    weight_percentage NUMERIC(5,2) NOT NULL,
    cutoff_score INT NOT NULL DEFAULT 600,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE scoring.scorecard_rules IS 'Master scorecard rules untuk kalkulasi credit scoring nasabah Bank Raya';
COMMENT ON COLUMN scoring.scorecard_rules.rule_id IS 'Primary key auto-increment scorecard rule';
COMMENT ON COLUMN scoring.scorecard_rules.rule_code IS 'Kode unik rule scorecard kredit (misal: SCR-MICRO-01)';
COMMENT ON COLUMN scoring.scorecard_rules.weight_percentage IS 'Bobot persentase kontribusi rule terhadap skor final';
COMMENT ON COLUMN scoring.scorecard_rules.cutoff_score IS 'Ambang batas nilai kelulusan kredit';

-- Transaksi Pengajuan Kredit Nasabah Digital
CREATE TABLE scoring.credit_applications (
    application_id UUID PRIMARY KEY,
    customer_cif VARCHAR(20) NOT NULL,
    rule_id INT NOT NULL,
    requested_amount NUMERIC(18,2) NOT NULL,
    tenor_months INT NOT NULL DEFAULT 12,
    risk_tier VARCHAR(5) NOT NULL,
    score_value INT NOT NULL,
    monthly_income NUMERIC(15,2) DEFAULT 0.00 NOT NULL,
    application_status VARCHAR(20) DEFAULT 'IN_REVIEW' NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT fk_credit_app_scorecard FOREIGN KEY (rule_id) 
        REFERENCES scoring.scorecard_rules(rule_id) ON DELETE RESTRICT
);

COMMENT ON TABLE scoring.credit_applications IS 'Transaksi pengajuan pinjaman digital nasabah retail dan mikro Bank Raya';
COMMENT ON COLUMN scoring.credit_applications.application_id IS 'UUID unik pengajuan pinjaman nasabah';
COMMENT ON COLUMN scoring.credit_applications.customer_cif IS 'Nomor CIF nasabah Bank Raya';
COMMENT ON COLUMN scoring.credit_applications.rule_id IS 'Foreign key ke master scorecard rules';
COMMENT ON COLUMN scoring.credit_applications.requested_amount IS 'Nominal pinjaman yang diajukan dalam IDR';
COMMENT ON COLUMN scoring.credit_applications.risk_tier IS 'Klasifikasi profil risiko (TIER_1 s.d TIER_5)';
COMMENT ON COLUMN scoring.credit_applications.score_value IS 'Nilai skor kredit hasil evaluasi engine';
COMMENT ON COLUMN scoring.credit_applications.monthly_income IS 'Estimasi penghasilan bulanan nasabah pemohon kredit';
COMMENT ON COLUMN scoring.credit_applications.application_status IS 'Status lifecycle pengajuan: IN_REVIEW, APPROVED, REJECTED, DISBURSED';

-- Indeks Kinerja Query
CREATE INDEX idx_scoring_cif ON scoring.credit_applications(customer_cif);
CREATE INDEX idx_scoring_status ON scoring.credit_applications(application_status);

CREATE TABLE scoring.fraud_audit_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES scoring.credit_applications(application_id),
    fraud_risk_score DECIMAL(5,2) NOT NULL,
    detection_rule VARCHAR(100) NOT NULL,
    flagged_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Master Daftar Hitam Nasabah Berisiko Tinggi
CREATE TABLE scoring.risk_blacklist (
    blacklist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_cif VARCHAR(20) NOT NULL,
    blacklist_reason VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    flagged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE scoring.risk_blacklist IS 'Daftar hitam risiko fraud dan penolakan kredit Bank Raya';
COMMENT ON COLUMN scoring.risk_blacklist.blacklist_id IS 'Primary key UUID catatan blacklist';
COMMENT ON COLUMN scoring.risk_blacklist.customer_cif IS 'Nomor CIF nasabah yang masuk daftar hitam';
COMMENT ON COLUMN scoring.risk_blacklist.blacklist_reason IS 'Alasan nasabah dimasukkan dalam daftar hitam';
