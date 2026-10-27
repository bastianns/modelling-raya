-- ==============================================================================
-- Bank Raya DAMA-DMBOK Data Architecture
-- Platform: MySQL 8.0 / MariaDB (OLTP - Channel Distribution & Partner Integrations)
-- Database/Schema: channel
-- Security: Zero-Credential-Exposure Static DDL
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS channel;
USE channel;

-- Transaksi Pencairan Pinjaman via Channel Mitra & Agen
CREATE TABLE channel.loan_disbursements (
    disbursement_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    application_id VARCHAR(36) NOT NULL COMMENT 'ID Pengajuan Kredit referensi ke scoring core engine',
    partner_channel_code VARCHAR(50) NOT NULL COMMENT 'Kode identifikasi mitra agregator / keagenan digital',
    account_destination VARCHAR(30) NOT NULL COMMENT 'Nomor rekening tujuan pencairan dana nasabah',
    disbursement_amount DECIMAL(18,2) NOT NULL COMMENT 'Nominal dana yang dicairkan ke nasabah',
    disbursement_fee DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Biaya administrasi / transfer pencairan',
    disbursement_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT 'Status pencairan: PENDING, SUCCESS, FAILED',
    channel_reference_id VARCHAR(100) UNIQUE NOT NULL COMMENT 'Nomor referensi settlement transaksi mitra',
    disbursed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Waktu eksekusi pencairan pinjaman',
    CONSTRAINT fk_disbursement_scoring_app FOREIGN KEY (application_id) 
        REFERENCES scoring.credit_applications(application_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Transaksi real-time pencairan pinjaman melalui mitra channel digital Bank Raya';

CREATE INDEX idx_disb_channel ON channel.loan_disbursements(partner_channel_code);
CREATE INDEX idx_disb_status ON channel.loan_disbursements(disbursement_status);
