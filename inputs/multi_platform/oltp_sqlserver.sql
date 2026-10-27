-- ==============================================================================
-- Bank Raya DAMA-DMBOK Data Architecture
-- Platform: Microsoft SQL Server (OLTP - Legacy Core Banking & Collateral Management)
-- Schema: legacy
-- Security: Zero-Credential-Exposure Static DDL
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = N'legacy')
BEGIN
    EXEC('CREATE SCHEMA [legacy]');
END
GO

-- Registrasi Agunan & Jaminan Kredit Legacy
CREATE TABLE [legacy].[collateral_registers] (
    [collateral_id] INT IDENTITY(1,1) NOT NULL,
    [customer_cif] NVARCHAR(20) NOT NULL,
    [collateral_type] NVARCHAR(50) NOT NULL,
    [certificate_number] NVARCHAR(100) NOT NULL,
    [owner_name] NVARCHAR(150) NOT NULL,
    [appraisal_value] DECIMAL(18,2) NOT NULL,
    [liquidation_value] DECIMAL(18,2) NOT NULL,
    [custody_branch_code] NVARCHAR(10) NOT NULL,
    [is_verified] BIT DEFAULT 1 NOT NULL,
    [registered_at] DATETIME2 DEFAULT GETDATE() NOT NULL,
    CONSTRAINT [PK_collateral_registers] PRIMARY KEY CLUSTERED ([collateral_id] ASC)
);
GO

-- Catatan Dokumentasi Enterprise Data Catalog
EXEC sys.sp_addextendedproperty 
    @name = N'MS_Description', @value = N'Master registrasi agunan kredit legacy yang dijamin oleh nasabah',
    @level0type = N'SCHEMA', @level0name = N'legacy',
    @level1type = N'TABLE', @level1name = N'collateral_registers';
GO

EXEC sys.sp_addextendedproperty 
    @name = N'MS_Description', @value = N'Nomor CIF nasabah pemilik agunan',
    @level0type = N'SCHEMA', @level0name = N'legacy',
    @level1type = N'TABLE', @level1name = N'collateral_registers',
    @level2type = N'COLUMN', @level2name = N'customer_cif';
GO
