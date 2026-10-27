-- ==============================================================================
-- Bank Raya DAMA-DMBOK Data Architecture
-- Platform: Apache Airflow (Batch ETL / ELT Orchestration)
-- Target: Google BigQuery Data Warehouse
-- DAG: dags_raya_credit_risk_pipeline
-- Schedule: 00 01 * * * (Daily Batch 01:00 UTC)
-- Lineage: dataraw.raw_applications -> datastaging.stg_applications -> datamart.fct_credit_scoring
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- TASK 1: Ingest & Normalize RAW ke STAGING (Idempotent Merge)
-- ------------------------------------------------------------------------------
MERGE INTO datastaging.stg_applications AS target
USING (
    SELECT 
        JSON_VALUE(payload_json, '$.application_id') AS application_id,
        JSON_VALUE(payload_json, '$.customer_cif') AS customer_cif,
        CAST(JSON_VALUE(payload_json, '$.rule_id') AS INT64) AS rule_id,
        CAST(JSON_VALUE(payload_json, '$.requested_amount') AS NUMERIC) AS requested_amount,
        JSON_VALUE(payload_json, '$.risk_tier') AS risk_tier,
        CAST(JSON_VALUE(payload_json, '$.score_value') AS INT64) AS score_value,
        COALESCE(JSON_VALUE(payload_json, '$.status'), 'PENDING') AS status,
        ingested_at
    FROM dataraw.raw_applications
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
) AS source
ON target.application_id = source.application_id
WHEN MATCHED THEN
    UPDATE SET 
        target.customer_cif = source.customer_cif,
        target.rule_id = source.rule_id,
        target.requested_amount = source.requested_amount,
        target.risk_tier = source.risk_tier,
        target.score_value = source.score_value,
        target.status = source.status,
        target.ingested_at = source.ingested_at
WHEN NOT MATCHED THEN
    INSERT (application_id, customer_cif, rule_id, requested_amount, risk_tier, score_value, status, ingested_at)
    VALUES (source.application_id, source.customer_cif, source.rule_id, source.requested_amount, source.risk_tier, source.score_value, source.status, source.ingested_at);

-- ------------------------------------------------------------------------------
-- TASK 2: Transformasi & Agregasi STAGING ke DATA MART Fact Credit Scoring
-- ------------------------------------------------------------------------------
INSERT INTO datamart.fct_credit_scoring (
    fact_id,
    application_id,
    customer_cif,
    credit_score,
    risk_tier,
    approved_amount,
    scoring_details,
    scoring_date
)
SELECT 
    GENERATE_UUID() AS fact_id,
    stg.application_id,
    stg.customer_cif,
    stg.score_value AS credit_score,
    CASE 
        WHEN stg.score_value >= 750 THEN 'TIER_1'
        WHEN stg.score_value >= 650 THEN 'TIER_2'
        WHEN stg.score_value >= 550 THEN 'TIER_3'
        ELSE 'TIER_4'
    END AS risk_tier,
    stg.requested_amount AS approved_amount,
    STRUCT(
        'v2.4.0' AS model_version,
        ROUND(CAST(0.015 * (850 - stg.score_value) / 100 AS NUMERIC), 4) AS probability_of_default,
        600 AS score_cutoff
    ) AS scoring_details,
    CURRENT_TIMESTAMP() AS scoring_date
FROM datastaging.stg_applications stg
LEFT JOIN datamart.fct_credit_scoring fct ON stg.application_id = fct.application_id
WHERE fct.fact_id IS NULL 
  AND stg.status IN ('APPROVED', 'DISBURSED');

-- ------------------------------------------------------------------------------
-- TASK 3: Agregasi SLIK OJK Monthly Snapshot
-- ------------------------------------------------------------------------------
INSERT INTO datamart.rpt_slik_ojk (
    report_id,
    period_yyyymm,
    account_number,
    customer_cif,
    collectibility_status,
    outstanding_balance,
    provision_amount,
    submission_status,
    created_at
)
SELECT
    GENERATE_UUID() AS report_id,
    FORMAT_TIMESTAMP('%Y%m', CURRENT_TIMESTAMP()) AS period_yyyymm,
    CONCAT('ACC-', SUBSTR(stg.application_id, 1, 8)) AS account_number,
    stg.customer_cif,
    '1' AS collectibility_status,
    stg.requested_amount AS outstanding_balance,
    ROUND(stg.requested_amount * 0.01, 2) AS provision_amount,
    'PENDING' AS submission_status,
    CURRENT_TIMESTAMP() AS created_at
FROM datastaging.stg_applications stg
LEFT JOIN datamart.rpt_slik_ojk rpt 
    ON rpt.customer_cif = stg.customer_cif 
   AND rpt.period_yyyymm = FORMAT_TIMESTAMP('%Y%m', CURRENT_TIMESTAMP())
WHERE rpt.report_id IS NULL
  AND stg.status = 'DISBURSED';
