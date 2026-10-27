# Enterprise Data Management (EDM) Stack: ChartDB & Azimutt Self-Hosted
## Bank Raya Multi-Platform Data Architecture (DAMA-DMBOK V.2)

Konfigurasi lokal dan orkestrasi perbankan enterprise (*Zero-Credential-Exposure* & *Zero Data Leakage*) yang mengintegrasikan seluruh ekosistem data Bank Raya ke dalam **ChartDB** (stateless diagramming) dan **Azimutt Self-Hosted** (enterprise metadata catalog & separated views).

---

## 🏛️ Arsitektur Integrasi Multi-Platform (DAMA-DMBOK V.2)

Ekosistem Data Management Bank Raya mengadopsi pilar **DAMA-DMBOK V.2** (*Data Modeling & Design*, *Data Architecture*, dan *Metadata Management & Governance*). Metadata dari 6 platform infrastruktur diekstrak secara statis tanpa kredensial aktif (*Zero-Credential-Exposure*), ditranspilasikan secara deterministik, dan diaudit melalui *Shift-Left Linter*.

```mermaid
flowchart TD
    subgraph SOURCELAYER["1. Sumber Metadata Multi-Platform (inputs/multi_platform/)"]
        PG["PostgreSQL 16 (Core OLTP)<br/>scoring.scorecard_rules<br/>scoring.credit_applications"]
        MY["MySQL 8.0 (Channel Partner)<br/>channel.loan_disbursements"]
        MS["SQL Server (Legacy Core)<br/>legacy.collateral_registers"]
        BQ["Google BigQuery (Medallion DWH)<br/>dataraw -> datastaging -> datamart"]
        DBT["dbt Core & Airflow Batch<br/>Data Contracts & Lineage ETL"]
        SS["Apache Superset<br/>BI Datasets & Executive Metrics"]
    end

    subgraph ENGINE["2. Transpiler & Shift-Left Linter (scripts/sync_multiplatform_metadata.py)"]
        TR["Deterministic Metadata Transpiler<br/>(Pure Python + PyYAML + sqlparse)"]
        LINT["Shift-Left Schema Linter<br/>WARN-01: Orphan Tables<br/>WARN-02: FK Type Mismatch<br/>WARN-03: PK & not_null Contracts"]
    end

    subgraph ARTIFACTS["3. Unified Metadata Artifacts (sources/ & layouts/)"]
        AZ_JSON["Azimutt Unified Schema JSON<br/>(bank_raya_unified_schema.json)"]
        CH_SQL["ChartDB Unified Import DDL<br/>(chartdb_unified_import.sql)"]
        AZ_LYT["Azimutt Domain Layouts<br/>(bank_raya_domain_layouts.json)"]
    end

    subgraph SERVING["4. Presentation & Visualization Layer"]
        CDB["ChartDB (:8080)<br/>100% Stateless ERD Engine"]
        AZM["Azimutt (:8000)<br/>Multi-Domain Metadata Explorer"]
        PG_DB[("Azimutt Internal PG<br/>(Isolated Backend DB)")]
    end

    PG --> TR
    MY --> TR
    MS --> TR
    BQ --> TR
    DBT --> TR
    SS --> TR

    TR --> LINT
    TR --> AZ_JSON
    TR --> CH_SQL
    TR --> AZ_LYT

    CH_SQL -.->|"Import SQL DDL"| CDB
    AZ_JSON -.->|"Load Schema"| AZM
    AZ_LYT -.->|"Apply Domain Views"| AZM
    AZM --- PG_DB
```

---

## 🛡️ Spesifikasi Keamanan & Hardening (Banking Grade)

1. **Layanan ChartDB (Stateless Diagramming)**:
   - **Base Image**: `ghcr.io/chartdb/chartdb:latest`
   - **Port**: `8080:80` (Akses langsung via [http://localhost:8080](http://localhost:8080))
   - **Environment Hardening**:
     - `DISABLE_ANALYTICS=true`: Menonaktifkan seluruh telemetri dan tracking analitik pihak ketiga.
     - `VITE_HIDE_CHARTDB_CLOUD=true`: Menyembunyikan menu SaaS/Cloud agar skema DDL tidak dapat diekspor ke cloud publik.
   - **100% Stateless**: Tanpa persistent volume mount. Data skema hanya berada di browser session pengguna.

2. **Layanan Azimutt (Self-Hosted Architecture)**:
   - **Base Image**: `ghcr.io/azimuttapp/azimutt:main`
   - **Port**: `8000:4000` (Akses langsung via [http://localhost:8000](http://localhost:8000))
   - **Pemisahan Penyimpanan (*Separated Storage*)**:
     - `./azimutt-data/sources:/app/sources`: Sumber skema statis (SQL DDL dan JSON resmi Azimutt).
     - `./azimutt-data/layouts:/app/layouts`: Konfigurasi posisi diagram visual (*views*) per domain DAMA-DMBOK agar sinkronisasi skema baru tidak merusak tata letak yang sudah dibuat.
     - `./azimutt-data/uploads:/app/bin/uploads`: Persistensi internal upload Azimutt.
   - **Isolasi Database Backend**: PostgreSQL 16 Alpine (`azimutt-backend-db`) terisolasi penuh di jaringan bridge internal **tanpa eksposur port ke host host komputer**.

3. **Topologi Jaringan Internal (`edm-secure-net`)**:
   - Seluruh kontainer berkomunikasi melalui user-defined bridge network `edm-secure-net`.

---

## 📂 Struktur Direktori Proyek

```text
modelling-raya/
├── .env                                         # Kredensial lokal terlindungi (Zero-Credential-Exposure)
├── .env.example                                 # Template referensi variabel lingkungan
├── .gitignore                                   # Mengabaikan .env dan venv dari git
├── docker-compose.yml                           # Orkestrasi Docker container (ChartDB & Azimutt)
├── inputs/
│   └── multi_platform/                         # 6 Sumber Metadata Statis Bank Raya
│       ├── oltp_postgres.sql                    # DDL PostgreSQL (Scoring & Scorecard Rules)
│       ├── oltp_mysql.sql                       # DDL MySQL (Channel Loan Disbursements)
│       ├── oltp_sqlserver.sql                   # DDL SQL Server (Legacy Collateral Registers)
│       ├── olap_bigquery_ddl.sql                # DDL BigQuery Medallion (Raw, Staging, Mart)
│       ├── dbt_schema.yml                       # Kontrak Data dbt (Data tests & Relationships)
│       ├── airflow_batch_query.sql              # Query Batch ETL Orkestrasi Airflow
│       └── superset_datasources.yaml            # Ekspor Dataset & Metrik BI Apache Superset
├── sources/                                     # Output Metadata Skema Terintegrasi
│   ├── bank_raya_unified_schema.json            # Format resmi Azimutt JsonSchema.elm (8 tabel, 4 relasi)
│   ├── chartdb_unified_import.sql               # DDL SQL terstandardisasi siap import di ChartDB
│   ├── bank_raya.azimutt.json                   # Project JSON lengkap Azimutt (8 tabel + 38 layout DASG)
│   └── autoload.html                            # Halaman auto-loader IndexedDB untuk ChartDB (:8080)
├── layouts/                                     # Output Domain Layouts DAMA-DMBOK
│   └── bank_raya_domain_layouts.json            # 38 domain layout (11 Domain DASG + Subdomain + Views)
├── azimutt-data/                                # Volume Terpasang pada Azimutt Container
│   ├── sources/                                 # Cermin tersinkronisasi /app/sources
│   ├── layouts/                                 # Cermin tersinkronisasi /app/layouts
│   ├── uploads/                                 # Volume internal uploads Azimutt
│   └── autoload_azimutt.html                    # Halaman auto-loader IndexedDB untuk Azimutt
├── docs/                                        # Output Dokumentasi Enterprise Offline
│   └── data_dictionary.html                     # Kamus Data Interaktif Mandiri (Audit-Ready)
├── scripts/
│   ├── launch.py                                # Single Master Orchestrator (Otomasi 1-Perintah)
│   ├── sync_multiplatform_metadata.py           # Transpiler deterministik & Shift-Left Linter (SSoT)
│   ├── seed_chartdb.py                          # Otomasi pre-loading ChartDB IndexedDB Dexie.js
│   ├── seed_azimutt.py                          # Otomasi pre-seeding Azimutt Postgres & Project
│   ├── generate_data_dictionary.py              # Generator Kamus Data HTML Standalone
│   ├── watch_and_sync.py                        # Daemon Live-Reload otomatis saat edit file DDL
│   └── verify_setup.py                          # Skrip audit hardening & validasi kepatuhan DAMA-DMBOK
└── venv/                                        # Virtual environment Python lokal
```

---

## ⚡ 5 Skenario Use Case Otomasi Enterprise (DataOps)

Sistem ini mendukung 5 siklus otomasi nyata di Bank Raya:

### Use Case 0: Single Master Command Zero-Manual (`scripts/launch.py`) ⭐
* **Kapan terjadi?** Saat developer atau arsitek data ingin menjalankan seluruh sistem tanpa repot copy-paste SQL atau upload file manual.
* **Alur Automasi**: Cukup ketik `python scripts/launch.py`. Skrip secara otomatis:
  1. Menghidupkan seluruh kontainer Docker (`chartdb-app`, `azimutt-app`, `azimutt-backend-db`).
  2. Mentranspilasikan 7 sumber multi-platform dengan *SSoT Deduplication* dan *Shift-Left Linter*.
  3. Memperbarui Kamus Data mandiri [docs/data_dictionary.html](file:///D:/modelling-raya/docs/data_dictionary.html).
  4. Menyuntikkan diagram langsung ke IndexedDB ChartDB (`http://localhost:8080/autoload.html`).
  5. Men-seeding database metadata dan project layout ke Azimutt (`http://localhost:8000`).
  6. Memverifikasi seluruh spesifikasi kepatuhan perbankan (31 test assertions 100% PASS).
  7. Membuka browser ke tampilan arsitektur yang sudah terisi lengkap.

### Use Case 1: Otomasi CI/CD & Gatekeeper PR (GitHub Actions)
* **Kapan terjadi?** Saat developer / data engineer melakukan `git push` atau membuat *Pull Request* baru.
* **Alur Automasi**: Pipeline [.github/workflows/data_ops_pipeline.yml](file:///D:/modelling-raya/.github/workflows/data_ops_pipeline.yml) otomatis berjalan di cloud.
  1. Menjalankan linter untuk mendeteksi `WARN-01` s.d. `WARN-03` dan `SSOT-01`.
  2. Memverifikasi struktur Docker Compose & Zero-Credential-Exposure.
  3. Mengarsip skema terbaru sebagai GitHub Actions artifact yang dapat diunduh dalam 1 klik.

### Use Case 2: Otomasi Live-Reload saat Coding Lokal (`watch_and_sync.py`)
* **Kapan terjadi?** Saat developer sedang merancang tabel baru di VS Code.
* **Alur Automasi**: Cukup jalankan `python scripts/watch_and_sync.py`. Setiap kali menekan `Ctrl + S` pada file SQL/YAML di `inputs/multi_platform/`, skrip otomatis mentranspilasi skema, merefresh file volume Azimutt, dan mengupdate kamus data tanpa perlu ketik perintah terminal berulang kali.

### Use Case 3: Otomasi Pembuatan Kamus Data HTML Offline untuk Auditor/Bisnis
* **Kapan terjadi?** Saat tim Compliance, Auditor OJK, atau pimpinan divisi meminta laporan dokumentasi data tanpa ingin membuka Docker/terminal.
* **Alur Automasi**: Jalankan `python scripts/generate_data_dictionary.py`. Menghasilkan satu file mandiri [docs/data_dictionary.html](file:///D:/modelling-raya/docs/data_dictionary.html) yang bisa langsung dibuka di browser Chrome/Edge secara offline, dilengkapi pencarian kolom, kamus data, dan diagram ERD Mermaid.

### Use Case 4: Otomasi Sinkronisasi Silsilah ETL Warehouse (Airflow Lineage Sync)
* **Kapan terjadi?** Setiap kali batch data mart BigQuery selesai diproses tengah malam oleh Apache Airflow.
* **Alur Automasi**: Task akhir Airflow memicu sinkronisasi metadata sehingga tabel data mart dan metrik Superset di katalog data selalu terbaharui secara harian tanpa intervensi manual.

---

## 🔍 Domain Layouts & Shift-Left Data Linter

### 1. Taksonomi 11 Domain DASG & Azimutt Layouts
Transpiler secara otomatis menyusun tabel ke dalam 11 Domain DASG dan 38 visual layouts pada [bank_raya_domain_layouts.json](file:///D:/modelling-raya/layouts/bank_raya_domain_layouts.json):
* **`oltp/core_and_channels`**: `scoring.credit_applications`, `scoring.scorecard_rules`, `channel.loan_disbursements`, `legacy.collateral_registers`.
* **`organize/bigquery_raw_to_mart`**: Medallion pipeline `dataraw.raw_applications` $\rightarrow$ `datastaging.stg_applications` $\rightarrow$ `datamart.fct_credit_scoring` & `datamart.rpt_slik_ojk`.
* **`deliver/superset_executive_bi`**: Tabel data mart yang dilengkapi metrik bisnis Superset (`avg_credit_score`, `total_approved_amount`, `npl_ratio`).
* **`teams/credit_scoring`**: End-to-end pemodelan credit risk dari aplikasi hingga data mart.
* **`teams/regulatory_reporting`**: Kepatuhan debitur dan agunan untuk laporan SLIK OJK.
* **`dasg/domain_01` s/d `dasg/domain_11`**: Pemetaan taksonomi 11 Domain Data Architecture Special Group (DASG) Bank Raya.

### 2. Shift-Left Schema Linter Rules
Linter berjalan otomatis untuk mendeteksi anomali integritas data enterprise:
* **`SSOT-01 (Single Source of Truth Deduplication)`**: Memvalidasi unifikasi entitas kanonikal lintas divisi dan memastikan tidak ada duplikasi tabel atau kolom.
* **`WARN-01 (Orphan Tables)`**: Mendeteksi tabel tanpa relasi foreign key masuk maupun keluar (`legacy.collateral_registers`, `datamart.rpt_slik_ojk`).
* **`WARN-02 (Foreign Key Type Mismatch)`**: Mendeteksi ketidaksesuaian tipe data lintas platform (contoh: `channel.loan_disbursements.application_id` bertipe `VARCHAR(36)` di MySQL mereferensikan `scoring.credit_applications.application_id` bertipe `UUID` di PostgreSQL).
* **`WARN-03 (Primary Key & Contract Check)`**: Memvalidasi eksistensi Primary Key dan konsistensi kontrak `not_null` pada dbt terhadap skema DDL.

---

## 🚀 Perintah Operasional Terminal

Pastikan virtual environment telah aktif:
```powershell
venv\Scripts\activate
```

### 1. Perintah Utama (Zero-Manual Launch) ⭐
Cukup jalankan satu perintah ini, seluruh kontainer, transpiler, seeding database, dan browser akan langsung terbuka dalam kondisi terisi lengkap:
```powershell
.\venv\Scripts\python.exe scripts\launch.py
```
*(Untuk mode headless tanpa membuka browser, gunakan flag `--no-browser`)*:
```powershell
.\venv\Scripts\python.exe scripts\launch.py --no-browser
```

### 2. Menjalankan Komponen Individual (Opsional)
* **Transpiler & Shift-Left Linter (SSoT)**:
  ```powershell
  .\venv\Scripts\python.exe scripts\sync_multiplatform_metadata.py
  ```
* **Pre-Seeding ChartDB**:
  ```powershell
  .\venv\Scripts\python.exe scripts\seed_chartdb.py
  ```
* **Pre-Seeding Azimutt**:
  ```powershell
  .\venv\Scripts\python.exe scripts\seed_azimutt.py
  ```
* **Audit Kepatuhan & Keamanan (Verify Setup)**:
  ```powershell
  .\venv\Scripts\python.exe scripts\verify_setup.py
  ```

### 3. Mengakses Endpoint Layanan
* **ChartDB (Otomatis Ter-Load)**: Buka [http://localhost:8080/autoload.html](http://localhost:8080/autoload.html) (otomatis menginjeksi IndexedDB dan membuka kanvas).
* **Azimutt (Otomatis Ter-Seeding)**: Buka [http://localhost:8000](http://localhost:8000) (Project *"Bank Raya Enterprise Data Architecture"* sudah siap).
* **Kamus Data HTML Mandiri**: Buka [docs/data_dictionary.html](file:///D:/modelling-raya/docs/data_dictionary.html).

### 4. Menghentikan Layanan (Down)
```powershell
docker compose down
```

---

## 📚 Referensi Arsitektur & Standar Kepatuhan Resmi (Plain Text URLs)

Berikut adalah daftar referensi primer yang digunakan sebagai landasan arsitektur, kepatuhan teknis, dan standar implementasi sistem ini:

1. Azimutt JSON Schema Specification (Elm Source Code):
   https://github.com
2. Azimutt Structured JSON Project & Import Documentation:
   https://github.com
3. Azimutt URL Query Parameter Auto-Loading (/create?sql= / ?json=):
   https://github.com
4. Azimutt Data Privacy & Local/IndexedDB Storage Structure:
   https://github.com
5. Azimutt Official Sources & Layouts Documentation:
   https://azimutt.app
   https://azimutt.app
6. ChartDB Official Dockerfile (Bukti nginx:stable-alpine melayani dari /usr/share/nginx/html):
   https://github.com
7. ChartDB Official Nginx Routing Config (Bukti try_files $uri $uri/ /index.html mengizinkan file statis langsung):
   https://github.com
8. ChartDB Official Issue #609 (Bukti penyimpanan state diagram di sisi client IndexedDB / Dexie.js):
   https://github.com
9. Standar W3C/MDN IndexedDB Same-Origin Policy & Port Isolation:
   https://mozilla.org
   https://mozilla.org
10. Docker CLI Official Docs untuk Injeksi Tanpa Volume/Port Terbuka (docker cp & docker exec):
    https://docker.com
    https://docker.com
11. Referensi Integrasi dbt YAML Properties & Apache Superset CLI Export:
    https://getdbt.com
    https://github.com
