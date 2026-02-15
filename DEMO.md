# BigLake Iceberg Pipeline — Demo Scenarios

Demo data: `thelook_ecommerce` from BigQuery public dataset (7 tables).
Initial data loaded via `test_data/thelook_ecommerce/seed.py`.
Incremental dirty batches generated via `test_data/thelook_ecommerce/generate.py`.

---

## 1. Data Ingestion Agent (Bronze Layer)

**What it shows:** Event-driven pipeline — dirty CSVs land in GCS, Eventarc triggers the data agent, agent cleans and exports to Parquet, loader creates/appends BigQuery Iceberg tables.

**Steps:**
1. Run `python test_data/thelook_ecommerce/seed.py` to load initial data from BigQuery public dataset
2. Generate incremental batches: `python test_data/thelook_ecommerce/generate.py`
3. Upload batch CSVs to `gs://<YOUR_INBOX_BUCKET>/{table_name}/`
4. Agent auto-detects format, normalizes columns, coerces types, flags duplicates, extracts currency symbols into `value_type` companion columns
5. Parquet lands in the staging bucket, loader creates/appends Iceberg tables in `bronze.*`

**Dirty data exercised:**
- Whitespace padding (15% of strings)
- Mixed case (category, status, gender)
- Null sentinels (N/A, none, -, missing, #N/A)
- Currency symbols ($, EUR, £, ¥) in price columns
- Date format variants (7 formats)
- Within-file duplicate rows (3%)

---

## 2. Data Prep (BigQuery Studio UI)

**What it shows:** Visual exploration of bronze data quality — no SQL required.

**Scenario:** Analyst opens `bronze.users` in Data Prep, profiles the data:
- Distribution of `gender`, `country`, `traffic_source`
- Null patterns across columns
- Value frequency for `is_duplicate_in_file`
- Type inspection (which columns stayed STRING vs got coerced)

Build a visual transformation that:
- Deduplicates by `id` (keep latest `processed_at`)
- Casts `age` to INT64, `created_at` to TIMESTAMP
- Standardizes `gender` M/F to Male/Female
- Filters rows where `email` IS NULL

**Persona:** Business analyst who explores before the engineering pipeline is built.

---

## 3. Data Engineering Agent (Gemini in BigQuery)

**What it shows:** Natural language → SQL pipeline generation.

### Bronze to Silver

Prompt the data engineering agent:

> "Create a silver.users table from bronze.users that deduplicates by id
> keeping the row with the most recent processed_at, casts age to INT64,
> standardizes gender M to Male and F to Female, and excludes rows where
> email is null."

> "Create a silver.orders table from bronze.orders that deduplicates by
> order_id, casts created_at/shipped_at/delivered_at/returned_at to
> TIMESTAMP, and standardizes status to title case."

> "Create a silver.order_items table from bronze.order_items that deduplicates
> by id, casts timestamps to TIMESTAMP, and normalizes sale_price to FLOAT64
> (drop the value_type column — we'll use it in gold)."

### Silver to Gold

> "Create a gold.customer_metrics table from silver.users joined with
> silver.orders and silver.order_items. Include: user_id, email, country,
> lifetime_order_count, total_spend, avg_order_value, first_order_at,
> last_order_at, return_rate, days_since_last_order, and a churn_flag
> that is TRUE when days_since_last_order exceeds 90."

> "Create a gold.product_performance table from silver.products joined
> with silver.order_items and silver.inventory_items. Include: product_id,
> name, category, brand, department, units_sold, total_revenue,
> avg_sale_price, return_count, return_rate, avg_margin_pct,
> inventory_turnover_ratio."

> "Create a gold.daily_sales table aggregated by date from silver.orders
> and silver.order_items. Include: sale_date, order_count, total_revenue,
> unique_customers, new_customers (first order that day), avg_basket_size."

---

## 4. Remote Function (Currency Conversion)

**What it shows:** BigQuery remote function calling Cloud Run for real-time enrichment.

**Scenario:** The agent extracted currency symbols into `sale_price_value_type`
(dollars, pounds, yen) during bronze ingestion. A remote function converts
all prices to USD using exchange rates.

**Architecture:**
- Cloud Run function accepts `(price FLOAT64, currency STRING)` → returns `FLOAT64` (USD)
- Registered as `bronze.convert_to_usd()` remote function in BigQuery
- Called during gold layer build:

```sql
SELECT
  oi.id,
  oi.sale_price,
  oi.sale_price_value_type,
  bronze.convert_to_usd(oi.sale_price, oi.sale_price_value_type) AS sale_price_usd
FROM silver.order_items oi
WHERE oi.sale_price_value_type IS NOT NULL
```

**Story arc:** Bronze has raw symbols → agent extracts semantic labels →
silver stores clean values with labels → gold normalizes to USD via remote function.

---

## 5. AI.GENERATE_TEXT (Address Standardization)

**What it shows:** Gemini called inline from SQL for intelligent data cleaning.

**Scenario:** User addresses in silver still have inconsistent formatting
(the agent cleaned whitespace/case, but can't validate addresses). Use
Gemini to standardize and validate.

```sql
SELECT
  u.id,
  u.street_address,
  u.city,
  u.state,
  u.country,
  AI.GENERATE_TEXT(
    MODEL `<YOUR_PROJECT_ID>.llm.gemini_2_5_flash`,
    CONCAT(
      'Standardize this address to USPS format. Return ONLY the formatted address, nothing else.\n',
      'Street: ', COALESCE(u.street_address, ''), '\n',
      'City: ', COALESCE(u.city, ''), '\n',
      'State: ', COALESCE(u.state, ''), '\n',
      'Country: ', COALESCE(u.country, '')
    )
  ).ml_generate_text_llm_result AS standardized_address
FROM silver.users u
WHERE u.country = 'United States'
LIMIT 50
```

**Alternative scenario:** Churn risk classification — pass user metrics
from `gold.customer_metrics` to Gemini for natural-language risk assessment.

---

## 6. Colab Enterprise Notebook (Cohort Retention Analysis)

**What it shows:** Interactive analysis with visualizations on the gold layer.

**Scenario:** Build a monthly cohort retention analysis:
1. Connect to BigQuery from Colab Enterprise
2. Pull `gold.customer_metrics` and `gold.daily_sales`
3. Assign users to cohorts by signup month (`first_order_at`)
4. Calculate retention: % of each cohort that ordered in months 1, 2, 3...
5. Visualize as a retention heatmap (seaborn/plotly)
6. Segment by `traffic_source` to compare acquisition channel quality

**Why a notebook:** Iterative exploration, chart output, cohort logic is
easier to express in Python than SQL, and the visualization is the deliverable.

**Bonus:** Embed product similarity using Vertex AI text embeddings on
product names, cluster with sklearn, visualize with UMAP. Shows the
Colab ↔ BigQuery ↔ Vertex AI triangle.

---

## 7. Vector Search + Auto-Embeddings (Gold Layer)

**What it shows:** BigQuery native vector search with auto-embeddings on
gold layer tables. Demonstrates Iceberg → BigQuery native table migration
for gold, unlocking vector indexes and BI Engine acceleration.

**Why native tables for gold:** Bronze and silver stay Iceberg (open format,
interoperable with Spark/Trino/etc). Gold migrates to BigQuery native to
unlock features that require managed storage: vector indexes, auto-embeddings,
BI Engine caching, materialized views.

### Product Similarity Search

1. Build `gold.product_catalog` (native table) from `silver.products` with a
   text column combining category, brand, and name:

```sql
CREATE TABLE `<YOUR_PROJECT_ID>.gold.product_catalog`
AS SELECT
  id AS product_id,
  name,
  category,
  brand,
  department,
  retail_price,
  CONCAT(category, ' - ', brand, ' ', name) AS description
FROM `<YOUR_PROJECT_ID>.silver.products`;
```

2. Create an embedding model connection and generate embeddings:

```sql
CREATE MODEL `<YOUR_PROJECT_ID>.gold.embedding_model`
  REMOTE WITH CONNECTION `<YOUR_PROJECT_ID>.us-central1.biglake-iceberg`
  OPTIONS (ENDPOINT = 'text-embedding-005');

ALTER TABLE `<YOUR_PROJECT_ID>.gold.product_catalog`
  ADD COLUMN description_embedding ARRAY<FLOAT64>;

UPDATE `<YOUR_PROJECT_ID>.gold.product_catalog` p
SET description_embedding = (
  SELECT ml_generate_embedding_result
  FROM ML.GENERATE_EMBEDDING(
    MODEL `<YOUR_PROJECT_ID>.gold.embedding_model`,
    (SELECT p.description AS content)
  )
);
```

3. Create a vector index for fast approximate nearest neighbor search:

```sql
CREATE VECTOR INDEX product_similarity_idx
ON `<YOUR_PROJECT_ID>.gold.product_catalog`(description_embedding)
OPTIONS (index_type = 'IVF', distance_type = 'COSINE');
```

4. Query: "Find products similar to this one":

```sql
SELECT
  query.name AS source_product,
  base.name AS similar_product,
  base.category,
  base.brand,
  distance
FROM VECTOR_SEARCH(
  TABLE `<YOUR_PROJECT_ID>.gold.product_catalog`,
  'description_embedding',
  (SELECT description_embedding FROM `<YOUR_PROJECT_ID>.gold.product_catalog` WHERE product_id = 42),
  top_k => 5,
  distance_type => 'COSINE'
)
ORDER BY distance;
```

### Auto-Embeddings on Incremental Data

Enable auto-embeddings so new products flowing through the pipeline
(bronze → silver → gold) are automatically embedded on load:

```sql
ALTER TABLE `<YOUR_PROJECT_ID>.gold.product_catalog`
SET OPTIONS (
  auto_embedding_columns = [('description', 'description_embedding')]
);
```

When new products are inserted into `gold.product_catalog` from silver,
BigQuery auto-generates embeddings — no additional pipeline step needed.

### Customer Embeddings (User Behavior)

Embed user behavior profiles for customer similarity and segmentation:

```sql
CREATE TABLE `<YOUR_PROJECT_ID>.gold.customer_profiles`
AS SELECT
  cm.user_id,
  cm.email,
  cm.country,
  CONCAT(
    'Customer with ', CAST(cm.lifetime_order_count AS STRING), ' orders, ',
    'total spend $', CAST(ROUND(cm.total_spend, 2) AS STRING), ', ',
    'avg order $', CAST(ROUND(cm.avg_order_value, 2) AS STRING), ', ',
    'return rate ', CAST(ROUND(cm.return_rate * 100, 1) AS STRING), '%, ',
    IF(cm.churn_flag, 'churned', 'active')
  ) AS behavior_summary
FROM `<YOUR_PROJECT_ID>.gold.customer_metrics` cm;
```

Then embed `behavior_summary` and use vector search to find customers
with similar purchasing patterns — useful for lookalike audiences and
personalized recommendations.

---

## Medallion Architecture Summary

| Layer | Format | Purpose | Tables |
|-------|--------|---------|--------|
| **Bronze** | Iceberg | Raw landing zone — agent-cleaned, append-only | distribution_centers, products, users, orders, order_items, inventory_items, events |
| **Silver** | Iceberg | Deduplicated, typed, standardized — single source of truth | users, products, orders, order_items, inventory_items, events |
| **Gold** | BigQuery Native | Business-ready — aggregations, enrichments, vector search | customer_metrics, product_performance, daily_sales, orders_enriched, users_enriched, product_catalog, customer_profiles |

**Why the format split:** Bronze/silver stay Iceberg for open format interoperability
(Spark, Trino, Presto can read directly from GCS). Gold migrates to BigQuery native
to unlock vector indexes, auto-embeddings, BI Engine caching, and materialized views.

### Gold Layer Tables

| Table | Type | Description |
|-------|------|-------------|
| `gold.customer_metrics` | Aggregation | Lifetime order count, total spend (USD), AOV, return rate, churn flag |
| `gold.product_performance` | Aggregation | Units sold, revenue, margin, return rate, inventory turnover |
| `gold.daily_sales` | Aggregation | Date-grain fact table — orders, revenue, new vs returning customers |
| `gold.orders_enriched` | Enrichment | Orders + user demographics + product details + USD-normalized prices |
| `gold.users_enriched` | Enrichment | Users + AI-standardized addresses + churn risk score |
| `gold.product_catalog` | Vector Search | Product descriptions with embeddings + auto-embed on insert |
| `gold.customer_profiles` | Vector Search | User behavior summaries with embeddings for lookalike audiences |

---

## Infrastructure

- **GCS Inbox Bucket:** raw file uploads (Eventarc trigger)
- **GCS Staging Bucket:** agent parquet output + reports (auto-delete 1 day)
- **GCS Iceberg Bucket:** BigQuery Iceberg table data (versioned)
- **GCS Archive Bucket:** archived originals (Nearline after 90 days)
- **BigQuery Datasets:** `bronze`, `silver`, `gold`
- **Iceberg Metastore:** BigLake Metastore (auto-registered via BigLake connection)
- **Cloud Run Services:** data-agent, file-loader, pipeline-logger
- **Eventarc:** GCS finalize → data-agent
- **Pub/Sub:** Topic A (LOAD_REQUEST) → file-loader, Topic B (events) → pipeline-logger
- **Firestore:** `pipeline-state` (file_registry, processing_locks)
- **GCP Project:** `<YOUR_PROJECT_ID>`
