-- ==============================================================================
-- Bank Raya DAMA-DMBOK Data Architecture
-- Platform: Google BigQuery (Enterprise Data Warehouse - OLAP)
-- Schemas / Datasets: dataraw, datastaging, datamart
-- Topology: 3-Layer Medallion Architecture (Raw -> Staging -> Mart)
-- Security: Zero-Credential-Exposure Static DDL
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. DATA RAW LAYER: Ingest mentah dari Change Data Capture (CDC) OLTP Core
-- ------------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS dataraw;

CREATE OR REPLACE TABLE dataraw.raw_applications (
    raw_id STRING NOT NULL,
    payload_json STRING,
    source_system STRING NOT NULL,
    kafka_offset INT64,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (raw_id) NOT ENFORCED
)
OPTIONS (
    description = "Penyimpanan data mentah pengajuan kredit dari CDC message broker"
);

-- ------------------------------------------------------------------------------
-- 2. DATA STAGING LAYER: Cleansing, deduplikasi, dan normalisasi tipe data
-- ------------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS datastaging;

CREATE OR REPLACE TABLE datastaging.stg_applications (
    application_id STRING NOT NULL,
    customer_cif STRING NOT NULL,
    rule_id INT64,
    requested_amount NUMERIC NOT NULL,
    risk_tier STRING,
    score_value INT64,
    status STRING NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    PRIMARY KEY (application_id) NOT ENFORCED,
    FOREIGN KEY (application_id) REFERENCES dataraw.raw_applications(raw_id) NOT ENFORCED
)
OPTIONS (
    description = "Staging data pengajuan pinjaman terstandarisasi siap dikonsumsi analitik"
);

-- ------------------------------------------------------------------------------
-- 3. DATA MART LAYER: Domain Credit Scoring Fact & Regulatory Reporting
-- ------------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS datamart;

-- Fakta Credit Scoring
CREATE OR REPLACE TABLE datamart.fct_credit_scoring (
    fact_id STRING NOT NULL,
    application_id STRING NOT NULL,
    customer_cif STRING NOT NULL,
    credit_score INT64 NOT NULL,
    risk_tier STRING NOT NULL,
    approved_amount NUMERIC NOT NULL,
    scoring_details STRUCT<
        model_version STRING,
        probability_of_default NUMERIC,
        score_cutoff INT64
    >,
    scoring_date TIMESTAMP NOT NULL,
    PRIMARY KEY (fact_id) NOT ENFORCED,
    FOREIGN KEY (application_id) REFERENCES datastaging.stg_applications(application_id) NOT ENFORCED
)
OPTIONS (
    description = "Fakta analitik credit scoring untuk pemodelan risiko dan portfolio debitur"
);

-- Laporan Kepatuhan Regulator SLIK OJK
CREATE OR REPLACE TABLE datamart.rpt_slik_ojk (
    report_id STRING NOT NULL,
    period_yyyymm STRING NOT NULL,
    account_number STRING NOT NULL,
    customer_cif STRING NOT NULL,
    collectibility_status STRING NOT NULL,
    outstanding_balance NUMERIC NOT NULL,
    provision_amount NUMERIC NOT NULL,
    submission_status STRING DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (report_id) NOT ENFORCED
)
OPTIONS (
    description = "Tabel data mart pelaporan berkala bulanan debitur ke regulator SLIK OJK"
);
