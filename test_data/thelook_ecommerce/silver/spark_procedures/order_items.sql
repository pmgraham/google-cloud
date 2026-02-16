CREATE OR REPLACE PROCEDURE `biglake-iceberg-datalake.silver.transform_order_items`()
WITH CONNECTION `biglake-iceberg-datalake.US.spark-proc`
OPTIONS (engine="SPARK", runtime_version="2.2")
LANGUAGE PYTHON AS R"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import LongType, DoubleType, StringType

spark = SparkSession.builder.appName("bronze-to-silver-order_items").getOrCreate()

PROJECT = "biglake-iceberg-datalake"
NULL_SENTINELS = {'N/A', 'NA', 'NONE', 'NULL', '-', '--', 'MISSING', '#N/A', ''}
DATE_FORMATS = [
    'yyyy-MM-dd HH:mm:ss',
    'yyyy/MM/dd HH:mm:ss',
    'MM/dd/yyyy HH:mm:ss',
    'MM-dd-yyyy HH:mm:ss',
    'MMM dd yyyy HH:mm:ss',
    'dd MMM yyyy HH:mm:ss',
    'MMMM dd, yyyy HH:mm:ss',
]

def null_sentinel_check(col_name):
    return F.when(
        F.upper(F.trim(F.col(col_name))).isin(list(NULL_SENTINELS)),
        F.lit(None).cast(StringType())
    ).otherwise(F.trim(F.col(col_name)))

def clean_string_initcap(col_name):
    return F.when(
        F.upper(F.trim(F.col(col_name))).isin(list(NULL_SENTINELS)),
        F.lit(None).cast(StringType())
    ).otherwise(F.initcap(F.trim(F.col(col_name))))

def clean_string_upper(col_name):
    return F.when(
        F.upper(F.trim(F.col(col_name))).isin(list(NULL_SENTINELS)),
        F.lit(None).cast(StringType())
    ).otherwise(F.upper(F.trim(F.col(col_name))))

def clean_string_lower(col_name):
    return F.when(
        F.upper(F.trim(F.col(col_name))).isin(list(NULL_SENTINELS)),
        F.lit(None).cast(StringType())
    ).otherwise(F.lower(F.trim(F.col(col_name))))

def clean_string_trim(col_name):
    return null_sentinel_check(col_name)

def parse_multi_format_timestamp(col_name):
    trimmed = F.trim(F.col(col_name))
    return F.coalesce(*[F.to_timestamp(trimmed, fmt) for fmt in DATE_FORMATS])

def safe_cast_to_long(col_name):
    c = F.col(col_name)
    return F.when(c == F.floor(c), c.cast(LongType())).otherwise(F.lit(None).cast(LongType()))

def expand_gender(col_name):
    trimmed_upper = F.upper(F.trim(F.col(col_name)))
    return (
        F.when(trimmed_upper.isin(list(NULL_SENTINELS)), F.lit(None).cast(StringType()))
        .when(trimmed_upper.isin('M', 'MALE'), F.lit('Male'))
        .when(trimmed_upper.isin('F', 'FEMALE'), F.lit('Female'))
        .otherwise(F.initcap(F.trim(F.col(col_name))))
    )

def format_state(col_name):
    cleaned = null_sentinel_check(col_name)
    return (
        F.when(cleaned.isNull(), F.lit(None).cast(StringType()))
        .when(F.length(cleaned) == 2, F.upper(cleaned))
        .otherwise(F.initcap(cleaned))
    )

def read_bronze(table_name):
    return spark.read.format("bigquery") \
        .option("table", f"{PROJECT}:bronze.{table_name}") \
        .load()

def write_silver(df, table_name):
    df.write.format("bigquery") \
        .option("table", f"{PROJECT}:silver.{table_name}") \
        .option("writeMethod", "direct") \
        .mode("overwrite") \
        .save()

def dedup(df, pk_col, ts_col="processed_at"):
    df = df.filter(F.col("is_duplicate_in_file") == False)
    w = Window.partitionBy(pk_col).orderBy(F.col(ts_col).desc())
    return df.withColumn("_row_rank", F.row_number().over(w)) \
             .filter(F.col("_row_rank") == 1) \
             .drop("_row_rank")

# ── Read and deduplicate ──
df = read_bronze("order_items")
df = dedup(df, "id")

# ── Transformations ──
# Cast id, order_id, user_id, product_id, inventory_item_id from FLOAT to LongType
df = df.withColumn("id", safe_cast_to_long("id"))
df = df.withColumn("order_id", safe_cast_to_long("order_id"))
df = df.withColumn("user_id", safe_cast_to_long("user_id"))
df = df.withColumn("product_id", safe_cast_to_long("product_id"))
df = df.withColumn("inventory_item_id", safe_cast_to_long("inventory_item_id"))

# Status: initcap
df = df.withColumn("status", clean_string_initcap("status"))

# Timestamps: created_at, shipped_at, delivered_at, returned_at STRING -> TIMESTAMP
df = df.withColumn("created_at", parse_multi_format_timestamp("created_at"))
df = df.withColumn("shipped_at", parse_multi_format_timestamp("shipped_at"))
df = df.withColumn("delivered_at", parse_multi_format_timestamp("delivered_at"))
df = df.withColumn("returned_at", parse_multi_format_timestamp("returned_at"))

# Normalize sale_price_value_type: any non-null/non-empty value becomes 'USD'
df = df.withColumn("sale_price_value_type",
    F.when(
        F.upper(F.trim(F.col("sale_price_value_type"))).isin(list(NULL_SENTINELS)) |
        F.col("sale_price_value_type").isNull(),
        F.lit(None).cast(StringType())
    ).otherwise(F.lit("USD"))
)

# Add silver_loaded_at timestamp
df = df.withColumn("silver_loaded_at", F.current_timestamp())

# ── Select final columns ──
df = df.select(
    "id",
    "order_id",
    "user_id",
    "product_id",
    "inventory_item_id",
    "status",
    "created_at",
    "shipped_at",
    "delivered_at",
    "returned_at",
    "sale_price",
    "sale_price_value_type",
    "silver_loaded_at"
)

# ── Write to silver ──
write_silver(df, "order_items")

# ── Export Iceberg metadata to BigLake Metastore ──
from google.cloud import bigquery
bq_client = bigquery.Client(project=PROJECT)
bq_client.query("EXPORT TABLE METADATA FROM `biglake-iceberg-datalake.silver.order_items`").result()
""";
