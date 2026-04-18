# Google Cloud Solutions & AI Monorepo

Welcome to the `google-cloud` monorepo. This repository serves as a consolidated hub for various data engineering, AI/ML, and cloud architecture solutions built on Google Cloud Platform. 

Each project within this monorepo is designed to solve specific challenges ranging from industrial data harmonization and natural language analysis to real-time data security and advanced BigQuery integrations.

---

## 📂 Repository Structure

| Project | Description | Technology Stack |
|:---|:---|:---|
| [**`vector-matching-rrf-pipeline`**](./vector-matching-rrf-pipeline) | Industrial parts catalog harmonization using Vector Search and AI reasoning agents. | BigQuery ML, Vector Search, Go, Vertex AI |
| [**`data-insights-agent`**](./data-insights-agent) | Natural language data analysis tool that enables querying BigQuery using plain English. | Google ADK, FastAPI, React, Vertex AI |
| [**`biglake-iceberg-pipeline`**](./biglake-iceberg-pipeline) | Event-driven data pipeline using BigQuery Iceberg tables and AI-powered cleaning agents. | BigLake, Iceberg, Cloud Run, Gemini |
| [**`google-cloud-bigquery-pii-masking-pipeline`**](./google-cloud-bigquery-pii-masking-pipeline) | Real-time PII masking pipeline for BigQuery data using Cloud DLP. | Dataflow, Cloud DLP, BigQuery |
| [**`bigquery-gemini-with-remote-functions`**](./bigquery-gemini-with-remote-functions) | Implementation of calling Gemini LLM models directly from BigQuery SQL. | BigQuery Remote Functions, Cloud Functions, Gemini |
| [**`bigquery-fuzzy-match-embeddings-example`**](./bigquery-fuzzy-match-embeddings-example) | Fuzzy record matching and customer deduplication using BigQuery embeddings. | BigQuery ML, Text Embeddings |
| [**`pdf-parsing-agent`**](./pdf-parsing-agent) | AI-powered PDF parsing agent that extracts text, tables, images, and OCR data from documents. | Google ADK, Gemini, PyMuPDF |

---

## 🚀 Project Overviews

### 1. Vector Matching RRF Pipeline
A dual-architecture approach to harmonizing disparate industrial parts catalogs. It utilizes BigQuery's native Vector Distance indexing for bulk resolution and an autonomous Go-based reasoning agent for complex edge-case verification.

### 2. Data Insights Agent
An intelligent interface for data analysis. It leverages the Google Agent Development Kit (ADK) to transform natural language questions into optimized SQL queries, providing instant insights and visualizations.

### 3. BigLake Iceberg Pipeline
Demonstrates modern open-table formats on Google Cloud. This pipeline processes data into Iceberg format using BigLake, with an integrated AI agent to ensure high data quality and automated schema alignment.

### 4. BQ PII Masking Pipeline
A security-first data pipeline that automatically detects and masks sensitive PII (Personally Identifiable Information) in real-time as data flows through BigQuery, ensuring compliance with privacy regulations.

### 5. BigQuery Gemini Remote Functions
A practical example showing how to extend BigQuery SQL with generative AI capabilities. By using remote functions, you can invoke Vertex AI's Gemini models directly within your SQL queries for text analysis, summarization, or translation.

### 6. BigQuery Fuzzy Match Embeddings
A specialized example for data deduplication. It uses BigQuery ML to generate embeddings for customer records and calculates similarity scores to find and match inconsistent records (e.g., spelling variations, different formats).

### 7. PDF Parsing Agent
An AI agent built with Google ADK that intelligently extracts structured content from PDF documents. It analyzes pages to determine document type (text-based vs scanned), then applies the appropriate extraction tools for text, tables, images, and OCR with word-level confidence scoring.

---

## 🛠️ How to Use This Repo

Each directory is a self-contained project. Navigate to the individual project folders to find specific deployment guides, prerequisites, and documentation.

```bash
# Example: Navigate to the Data Insights Agent
cd data-insights-agent
```

## 📜 License

Most projects within this monorepo are licensed under the MIT License. Please check the `LICENSE` file within each project directory for specific terms.
