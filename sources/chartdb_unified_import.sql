-- ==============================================================================
-- Bank Raya - ChartDB Unified Multi-Platform ERD Import DDL
-- Architecture: DAMA-DMBOK V.2 Integrated Data Architecture
-- Target: ChartDB Stateless Diagramming Engine (:8080)
-- Zero-Credential-Exposure: Sanitized Schema Definitions
-- ==============================================================================

CREATE SCHEMA IF NOT EXISTS channel;
CREATE SCHEMA IF NOT EXISTS datamart;
CREATE SCHEMA IF NOT EXISTS dataraw;
CREATE SCHEMA IF NOT EXISTS datastaging;
CREATE SCHEMA IF NOT EXISTS legacy;
CREATE SCHEMA IF NOT EXISTS scoring;

-- ------------------------------------------------------------------------------
-- Platform: Google BigQuery (OLAP Data Lakehouse - Mart)
-- Table: datamart.rpt_slik_ojk
-- ------------------------------------------------------------------------------
CREATE TABLE datamart.rpt_slik_ojk (
    report_id VARCHAR(255) NOT NULL,
    period_yyyymm VARCHAR(255) NOT NULL,
    account_number VARCHAR(255) NOT NULL,
    customer_cif VARCHAR(255) NOT NULL,
    collectibility_status VARCHAR(255) NOT NULL,
    outstanding_balance NUMERIC NOT NULL,
    provision_amount NUMERIC NOT NULL,
    submission_status VARCHAR(255) NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_rpt_slik_ojk PRIMARY KEY (report_id)
);

COMMENT ON TABLE datamart.rpt_slik_ojk IS 'Tabel data mart pelaporan berkala bulanan debitur ke regulator SLIK OJK | DASG: domain_05/subdomain_05_1 | dbt Model: Data Mart Pelaporan Kepatuhan Regulator SLIK OJK Bulanan [Airflow Orchestrated: DAG dags_raya_credit_risk_pipeline @daily] [Superset Metrics: total_outstanding (SUM(outstanding_balance)): Total baki debet pinjaman aktif seluruh debitur; npl_ratio (SUM(CASE WHEN collectibility_status IN (''3'',''4'',''5'') THEN outstanding_balance ELSE 0 END) / NULLIF(SUM(outstanding_balance), 0) * 100): Persentase rasio kredit macet/bermasalah (NPL) Bank Raya]';
COMMENT ON COLUMN datamart.rpt_slik_ojk.report_id IS 'Primary key baris pelaporan bulanan SLIK OJK';
COMMENT ON COLUMN datamart.rpt_slik_ojk.period_yyyymm IS 'Periode akuntansi pelaporan format tahun-bulan (YYYYMM)';
COMMENT ON COLUMN datamart.rpt_slik_ojk.account_number IS 'Nomor rekening fasilitas kredit debitur';
COMMENT ON COLUMN datamart.rpt_slik_ojk.customer_cif IS 'Nomor CIF nasabah debitur';
COMMENT ON COLUMN datamart.rpt_slik_ojk.collectibility_status IS 'Kolektibilitas debitur per POJK (1: Lancar, 2: DPK, 3: Kurang Lancar, 4: Diragukan, 5: Macet)';
COMMENT ON COLUMN datamart.rpt_slik_ojk.outstanding_balance IS 'Total saldo pokok pinjaman aktif';
COMMENT ON COLUMN datamart.rpt_slik_ojk.provision_amount IS 'Cadangan Kerugian Penurunan Nilai (CKPN)';
COMMENT ON COLUMN datamart.rpt_slik_ojk.submission_status IS 'Status pelaporan ke OJK (PENDING, SUBMITTED, APPROVED)';
COMMENT ON COLUMN datamart.rpt_slik_ojk.created_at IS 'Waktu pembentukan data agregasi';

-- ------------------------------------------------------------------------------
-- Platform: Google BigQuery (OLAP Data Lakehouse - Raw)
-- Table: dataraw.raw_applications
-- ------------------------------------------------------------------------------
CREATE TABLE dataraw.raw_applications (
    raw_id VARCHAR(255) NOT NULL,
    payload_json VARCHAR(255) NULL,
    source_system VARCHAR(255) NOT NULL,
    kafka_offset BIGINT NULL,
    ingested_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_raw_applications PRIMARY KEY (raw_id)
);

COMMENT ON TABLE dataraw.raw_applications IS 'Penyimpanan data mentah pengajuan kredit dari CDC message broker | DASG: domain_06/subdomain_06_1 | dbt Source: Data mentah payload pengajuan kredit CDC message broker';
COMMENT ON COLUMN dataraw.raw_applications.raw_id IS 'Surrogate identifier mentah ingestion data';
COMMENT ON COLUMN dataraw.raw_applications.payload_json IS 'JSON string representasi event transaksi pengajuan kredit';
COMMENT ON COLUMN dataraw.raw_applications.source_system IS 'Nama sistem pengirim transaksi (misal: OLTP_CORE_POSTGRES)';
COMMENT ON COLUMN dataraw.raw_applications.kafka_offset IS 'Offset Kafka message partition';
COMMENT ON COLUMN dataraw.raw_applications.ingested_at IS 'Waktu ingestion ke BigQuery';

-- ------------------------------------------------------------------------------
-- Platform: Microsoft SQL Server (Legacy Core OLTP)
-- Table: legacy.collateral_registers
-- ------------------------------------------------------------------------------
CREATE TABLE legacy.collateral_registers (
    collateral_id INT NOT NULL,
    customer_cif VARCHAR(20) NOT NULL,
    collateral_type VARCHAR(50) NOT NULL,
    certificate_number VARCHAR(100) NOT NULL,
    owner_name VARCHAR(150) NOT NULL,
    appraisal_value DECIMAL(18,2) NOT NULL,
    liquidation_value DECIMAL(18,2) NOT NULL,
    custody_branch_code VARCHAR(10) NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT 1,
    registered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT GETDATE(),
    CONSTRAINT PK_collateral_registers PRIMARY KEY (collateral_id)
);

COMMENT ON TABLE legacy.collateral_registers IS 'Master registrasi agunan kredit legacy yang dijamin oleh nasabah | DASG: domain_04/subdomain_04_1 | dbt Source: Master registrasi agunan kredit nasabah';
COMMENT ON COLUMN legacy.collateral_registers.collateral_id IS 'Identity primary key agunan';
COMMENT ON COLUMN legacy.collateral_registers.customer_cif IS 'Nomor CIF nasabah pemilik agunan';
COMMENT ON COLUMN legacy.collateral_registers.collateral_type IS 'Jenis agunan (SHM, BPKB, Deposito)';
COMMENT ON COLUMN legacy.collateral_registers.certificate_number IS 'Nomor sertifikat bukti kepemilikan agunan';
COMMENT ON COLUMN legacy.collateral_registers.owner_name IS 'Nama pemilik yang tertera di sertifikat agunan';
COMMENT ON COLUMN legacy.collateral_registers.appraisal_value IS 'Nilai pasar hasil taksasi agunan';
COMMENT ON COLUMN legacy.collateral_registers.liquidation_value IS 'Nilai likuidasi agunan';
COMMENT ON COLUMN legacy.collateral_registers.custody_branch_code IS 'Kode unit cabang penyimpanan fisik dokumen jaminan';
COMMENT ON COLUMN legacy.collateral_registers.is_verified IS 'Flag verifikasi keaslian dokumen agunan';
COMMENT ON COLUMN legacy.collateral_registers.registered_at IS 'Waktu pencatatan agunan';

-- ------------------------------------------------------------------------------
-- Platform: PostgreSQL 16 (Core OLTP)
-- Table: scoring.risk_blacklist
-- ------------------------------------------------------------------------------
CREATE TABLE scoring.risk_blacklist (
    blacklist_id UUID NOT NULL DEFAULT gen_random_uuid(),
    customer_cif VARCHAR(20) NOT NULL,
    blacklist_reason VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    flagged_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_risk_blacklist PRIMARY KEY (blacklist_id)
);

COMMENT ON TABLE scoring.risk_blacklist IS 'Daftar hitam risiko fraud dan penolakan kredit Bank Raya';
COMMENT ON COLUMN scoring.risk_blacklist.blacklist_id IS 'Primary key UUID catatan blacklist';
COMMENT ON COLUMN scoring.risk_blacklist.customer_cif IS 'Nomor CIF nasabah yang masuk daftar hitam';
COMMENT ON COLUMN scoring.risk_blacklist.blacklist_reason IS 'Alasan nasabah dimasukkan dalam daftar hitam';
COMMENT ON COLUMN scoring.risk_blacklist.is_active IS 'Field is_active pada scoring.risk_blacklist';
COMMENT ON COLUMN scoring.risk_blacklist.flagged_at IS 'Field flagged_at pada scoring.risk_blacklist';

-- ------------------------------------------------------------------------------
-- Platform: PostgreSQL 16 (Core OLTP) + PostgreSQL OLTP
-- Table: scoring.scorecard_rules
-- ------------------------------------------------------------------------------
CREATE TABLE scoring.scorecard_rules (
    rule_id SERIAL NOT NULL,
    rule_code VARCHAR(50) NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    weight_percentage NUMERIC(5,2) NOT NULL,
    cutoff_score INT NOT NULL DEFAULT 600,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_scorecard_rules PRIMARY KEY (rule_id)
);

COMMENT ON TABLE scoring.scorecard_rules IS 'Master scorecard rules untuk kalkulasi credit scoring nasabah Bank Raya | DASG: domain_02/subdomain_02_1 | dbt Source: Master aturan pembobotan scorecard evaluasi risiko';
COMMENT ON COLUMN scoring.scorecard_rules.rule_id IS 'Primary key auto-increment scorecard rule';
COMMENT ON COLUMN scoring.scorecard_rules.rule_code IS 'Kode unik rule scorecard kredit (misal: SCR-MICRO-01)';
COMMENT ON COLUMN scoring.scorecard_rules.rule_name IS 'Nama deskriptif scorecard rule | Field rule_name pada scoring.scorecard_rules';
COMMENT ON COLUMN scoring.scorecard_rules.weight_percentage IS 'Bobot persentase kontribusi rule terhadap skor final';
COMMENT ON COLUMN scoring.scorecard_rules.cutoff_score IS 'Ambang batas nilai kelulusan kredit';
COMMENT ON COLUMN scoring.scorecard_rules.is_active IS 'Flag status keaktifan rule | Field is_active pada scoring.scorecard_rules';
COMMENT ON COLUMN scoring.scorecard_rules.created_at IS 'Waktu pembuatan record | Field created_at pada scoring.scorecard_rules';
COMMENT ON COLUMN scoring.scorecard_rules.updated_at IS 'Waktu pembaruan record | Field updated_at pada scoring.scorecard_rules';

-- ------------------------------------------------------------------------------
-- Platform: Google BigQuery (OLAP Data Lakehouse - Staging)
-- Table: datastaging.stg_applications
-- ------------------------------------------------------------------------------
CREATE TABLE datastaging.stg_applications (
    application_id VARCHAR(255) NOT NULL,
    customer_cif VARCHAR(255) NOT NULL,
    rule_id BIGINT NULL,
    requested_amount NUMERIC NOT NULL,
    risk_tier VARCHAR(255) NULL,
    score_value BIGINT NULL,
    status VARCHAR(255) NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    CONSTRAINT pk_stg_applications PRIMARY KEY (application_id)
);

COMMENT ON TABLE datastaging.stg_applications IS 'Staging data pengajuan pinjaman terstandarisasi siap dikonsumsi analitik | DASG: domain_07/subdomain_07_1 | dbt Model: Model staging terstandarisasi untuk pengajuan kredit digital Bank Raya [Airflow Orchestrated: DAG dags_raya_credit_risk_pipeline @daily]';
COMMENT ON COLUMN datastaging.stg_applications.application_id IS 'ID pengajuan pinjaman (UUID string terstandarisasi)';
COMMENT ON COLUMN datastaging.stg_applications.customer_cif IS 'Nomor identifikasi unik nasabah (Customer Information File)';
COMMENT ON COLUMN datastaging.stg_applications.rule_id IS 'ID rule scorecard kredit';
COMMENT ON COLUMN datastaging.stg_applications.requested_amount IS 'Nominal pengajuan plafond kredit dalam Rupiah';
COMMENT ON COLUMN datastaging.stg_applications.risk_tier IS 'Kategori risiko kredit';
COMMENT ON COLUMN datastaging.stg_applications.score_value IS 'Nilai skor kredit evaluasi engine';
COMMENT ON COLUMN datastaging.stg_applications.status IS 'Status verifikasi pengajuan kredit';
COMMENT ON COLUMN datastaging.stg_applications.ingested_at IS 'Waktu normalisasi staging';

-- ------------------------------------------------------------------------------
-- Platform: Google BigQuery (OLAP Data Lakehouse - Mart)
-- Table: datamart.fct_credit_scoring
-- ------------------------------------------------------------------------------
CREATE TABLE datamart.fct_credit_scoring (
    fact_id VARCHAR(255) NOT NULL,
    application_id VARCHAR(255) NOT NULL,
    customer_cif VARCHAR(255) NOT NULL,
    credit_score BIGINT NOT NULL,
    risk_tier VARCHAR(255) NOT NULL,
    approved_amount NUMERIC NOT NULL,
    scoring_details JSON NULL,
    scoring_date TIMESTAMP NOT NULL,
    CONSTRAINT pk_fct_credit_scoring PRIMARY KEY (fact_id)
);

COMMENT ON TABLE datamart.fct_credit_scoring IS 'Fakta analitik credit scoring untuk pemodelan risiko dan portfolio debitur | DASG: domain_08/subdomain_08_1 | dbt Model: Data Mart Fakta Credit Scoring untuk evaluasi risiko dan limit debitur [Airflow Orchestrated: DAG dags_raya_credit_risk_pipeline @daily] [Superset Metrics: avg_credit_score (AVG(credit_score)): Rata-rata skor kredit nasabah yang disetujui; total_approved_amount (SUM(approved_amount)): Total akumulasi plafond kredit yang disetujui; high_risk_exposure (COUNT(CASE WHEN risk_tier IN (''TIER_3'', ''TIER_4'', ''TIER_5'') THEN 1 END)): Jumlah aplikasi pinjaman dengan profil risiko tinggi]';
COMMENT ON COLUMN datamart.fct_credit_scoring.fact_id IS 'Surrogate key fakta penilaian kredit';
COMMENT ON COLUMN datamart.fct_credit_scoring.application_id IS 'Relasi foreign key ke tabel staging pengajuan pinjaman';
COMMENT ON COLUMN datamart.fct_credit_scoring.customer_cif IS 'Nomor CIF nasabah yang dinilai skor kreditnya';
COMMENT ON COLUMN datamart.fct_credit_scoring.credit_score IS 'Nilai skor kredit terhitung (skala 300 - 850)';
COMMENT ON COLUMN datamart.fct_credit_scoring.risk_tier IS 'Klasifikasi profil risiko nasabah (TIER_1 s.d. TIER_5)';
COMMENT ON COLUMN datamart.fct_credit_scoring.approved_amount IS 'Nominal plafond yang disetujui';
COMMENT ON COLUMN datamart.fct_credit_scoring.scoring_details IS 'Struktur detail model statistik machine learning';
COMMENT ON COLUMN datamart.fct_credit_scoring.scoring_date IS 'Tanggal dan waktu evaluasi credit scoring';

-- ------------------------------------------------------------------------------
-- Platform: PostgreSQL 16 (Core OLTP) + PostgreSQL OLTP
-- Table: scoring.credit_applications
-- ------------------------------------------------------------------------------
CREATE TABLE scoring.credit_applications (
    application_id UUID NOT NULL,
    customer_cif VARCHAR(20) NOT NULL,
    rule_id INT NOT NULL,
    requested_amount NUMERIC(18,2) NOT NULL,
    tenor_months INT NOT NULL DEFAULT 12,
    risk_tier VARCHAR(5) NOT NULL,
    score_value INT NOT NULL,
    monthly_income NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    application_status VARCHAR(20) NOT NULL DEFAULT 'IN_REVIEW',
    submitted_at TIMESTAMP WITH TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP WITH TIME ZONE NULL,
    CONSTRAINT pk_credit_applications PRIMARY KEY (application_id)
);

COMMENT ON TABLE scoring.credit_applications IS 'Transaksi pengajuan pinjaman digital nasabah retail dan mikro Bank Raya | DASG: domain_02/subdomain_02_2 | dbt Source: Pengajuan pinjaman debitur digital Bank Raya';
COMMENT ON COLUMN scoring.credit_applications.application_id IS 'UUID unik pengajuan pinjaman nasabah';
COMMENT ON COLUMN scoring.credit_applications.customer_cif IS 'Nomor CIF nasabah Bank Raya';
COMMENT ON COLUMN scoring.credit_applications.rule_id IS 'Foreign key ke master scorecard rules';
COMMENT ON COLUMN scoring.credit_applications.requested_amount IS 'Nominal pinjaman yang diajukan dalam IDR';
COMMENT ON COLUMN scoring.credit_applications.tenor_months IS 'Jangka waktu pinjaman dalam bulan | Field tenor_months pada scoring.credit_applications';
COMMENT ON COLUMN scoring.credit_applications.risk_tier IS 'Klasifikasi profil risiko (TIER_1 s.d TIER_5)';
COMMENT ON COLUMN scoring.credit_applications.score_value IS 'Nilai skor kredit hasil evaluasi engine';
COMMENT ON COLUMN scoring.credit_applications.monthly_income IS 'Estimasi penghasilan bulanan nasabah pemohon kredit';
COMMENT ON COLUMN scoring.credit_applications.application_status IS 'Status lifecycle pengajuan: IN_REVIEW, APPROVED, REJECTED, DISBURSED';
COMMENT ON COLUMN scoring.credit_applications.submitted_at IS 'Waktu pengajuan diajukan | Field submitted_at pada scoring.credit_applications';
COMMENT ON COLUMN scoring.credit_applications.approved_at IS 'Waktu persetujuan pinjaman | Field approved_at pada scoring.credit_applications';

-- ------------------------------------------------------------------------------
-- Platform: MySQL 8.0 / MariaDB (Channel OLTP)
-- Table: channel.loan_disbursements
-- ------------------------------------------------------------------------------
CREATE TABLE channel.loan_disbursements (
    disbursement_id BIGINT NOT NULL,
    application_id VARCHAR(36) NOT NULL,
    partner_channel_code VARCHAR(50) NOT NULL,
    account_destination VARCHAR(30) NOT NULL,
    disbursement_amount DECIMAL(18,2) NOT NULL,
    disbursement_fee DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    disbursement_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    channel_reference_id VARCHAR(100) NOT NULL,
    disbursed_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_loan_disbursements PRIMARY KEY (disbursement_id)
);

COMMENT ON TABLE channel.loan_disbursements IS 'Transaksi real-time pencairan pinjaman melalui mitra channel digital Bank Raya | DASG: domain_03/subdomain_03_1 | dbt Source: Transaksi pencairan pinjaman via agen dan fintech partner';
COMMENT ON COLUMN channel.loan_disbursements.disbursement_id IS 'Surrogate primary key auto increment';
COMMENT ON COLUMN channel.loan_disbursements.application_id IS 'ID Pengajuan Kredit referensi ke scoring core engine';
COMMENT ON COLUMN channel.loan_disbursements.partner_channel_code IS 'Kode identifikasi mitra agregator / keagenan digital';
COMMENT ON COLUMN channel.loan_disbursements.account_destination IS 'Nomor rekening tujuan pencairan dana nasabah';
COMMENT ON COLUMN channel.loan_disbursements.disbursement_amount IS 'Nominal dana yang dicairkan ke nasabah';
COMMENT ON COLUMN channel.loan_disbursements.disbursement_fee IS 'Biaya administrasi / transfer pencairan';
COMMENT ON COLUMN channel.loan_disbursements.disbursement_status IS 'Status pencairan: PENDING, SUCCESS, FAILED';
COMMENT ON COLUMN channel.loan_disbursements.channel_reference_id IS 'Nomor referensi settlement transaksi mitra';
COMMENT ON COLUMN channel.loan_disbursements.disbursed_at IS 'Waktu eksekusi pencairan pinjaman';

-- ------------------------------------------------------------------------------
-- Platform: PostgreSQL 16 (Core OLTP)
-- Table: scoring.fraud_audit_events
-- ------------------------------------------------------------------------------
CREATE TABLE scoring.fraud_audit_events (
    event_id UUID NOT NULL DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL,
    fraud_risk_score DECIMAL(5,2) NOT NULL,
    detection_rule VARCHAR(100) NOT NULL,
    flagged_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fraud_audit_events PRIMARY KEY (event_id)
);

COMMENT ON TABLE scoring.fraud_audit_events IS 'Tabel scoring.fraud_audit_events | DASG: domain_02/subdomain_02_2 | dbt Source: Event audit kecurangan dan log deteksi anomali pada aplikasi underwriting kredit';
COMMENT ON COLUMN scoring.fraud_audit_events.event_id IS 'Primary key identifier event audit fraud';
COMMENT ON COLUMN scoring.fraud_audit_events.application_id IS 'Foreign key referensi ke scoring.credit_applications';
COMMENT ON COLUMN scoring.fraud_audit_events.fraud_risk_score IS 'Skor risiko kecurangan hasil kalkulasi model anomali';
COMMENT ON COLUMN scoring.fraud_audit_events.detection_rule IS 'Aturan atau model deteksi yang menandai event';
COMMENT ON COLUMN scoring.fraud_audit_events.flagged_at IS 'Waktu deteksi event anomali kecurangan dicatat';

-- ==============================================================================
-- Cross-Platform Foreign Key & Lineage Relationships
-- ==============================================================================
ALTER TABLE scoring.credit_applications ADD CONSTRAINT fk_credit_app_scorecard FOREIGN KEY (rule_id) REFERENCES scoring.scorecard_rules(rule_id);
ALTER TABLE scoring.fraud_audit_events ADD CONSTRAINT fk_fraud_audit_events_application_id FOREIGN KEY (application_id) REFERENCES scoring.credit_applications(application_id);
ALTER TABLE channel.loan_disbursements ADD CONSTRAINT fk_disbursement_scoring_app FOREIGN KEY (application_id) REFERENCES scoring.credit_applications(application_id);
ALTER TABLE datastaging.stg_applications ADD CONSTRAINT fk_stg_raw_applications FOREIGN KEY (application_id) REFERENCES dataraw.raw_applications(raw_id);
ALTER TABLE datamart.fct_credit_scoring ADD CONSTRAINT fk_fct_stg_applications FOREIGN KEY (application_id) REFERENCES datastaging.stg_applications(application_id);

-- End of ChartDB Unified Import SQL
