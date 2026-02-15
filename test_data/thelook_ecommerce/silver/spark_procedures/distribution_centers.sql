CREATE OR REPLACE PROCEDURE `biglake-pipeline-test1.silver.transform_distribution_centers`()
WITH CONNECTION `biglake-pipeline-test1.US.spark-proc`
OPTIONS (engine="SPARK", runtime_version="2.2")
LANGUAGE PYTHON AS R"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import LongType, DoubleType, StringType

spark = SparkSession.builder.appName("bronze-to-silver-distribution_centers").getOrCreate()

PROJECT = "biglake-pipeline-test1"
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
df = read_bronze("distribution_centers")
df = dedup(df, "id")

# ── Transformations ──
# Cast id from FLOAT to LongType
df = df.withColumn("id", safe_cast_to_long("id"))

# Clean name with initcap
df = df.withColumn("name", clean_string_initcap("name"))

# Split name into city and state
# Extract the last whitespace-delimited token as state (e.g. "TN", "NY/NJ")
# Everything before that token becomes city
df = df.withColumn("_state_token", F.regexp_extract(F.col("name"), r'(\S+)\s*$', 1))
df = df.withColumn("state", F.upper(F.col("_state_token")))
df = df.withColumn("city", F.initcap(F.trim(
    F.regexp_replace(F.col("name"), r'\s+\S+\s*$', '')
)))
df = df.drop("_state_token")

# Add silver_loaded_at timestamp
df = df.withColumn("silver_loaded_at", F.current_timestamp())

# ── Select final columns ──
df = df.select(
    "id",
    "name",
    "city",
    "state",
    "latitude",
    "longitude",
    "silver_loaded_at"
)

# ── Write to silver ──
write_silver(df, "distribution_centers")

# ── Export Iceberg metadata to BigLake Metastore ──
from google.cloud import bigquery
bq_client = bigquery.Client(project=PROJECT)
bq_client.query("EXPORT TABLE METADATA FROM `biglake-pipeline-test1.silver.distribution_centers`").result()
""";
