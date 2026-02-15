CREATE OR REPLACE PROCEDURE `biglake-pipeline-test1.silver.transform_users`()
WITH CONNECTION `biglake-pipeline-test1.US.spark-proc`
OPTIONS (engine="SPARK", runtime_version="2.2")
LANGUAGE PYTHON AS R"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import LongType, DoubleType, StringType

spark = SparkSession.builder.appName("bronze-to-silver-users").getOrCreate()

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
df = read_bronze("users")
df = dedup(df, "id")

# ── Transformations ──
# Cast id from INTEGER to LongType, age from FLOAT to LongType
df = df.withColumn("id", F.col("id").cast(LongType()))
df = df.withColumn("age", safe_cast_to_long("age"))

# Clean first_name, last_name with initcap
df = df.withColumn("first_name", clean_string_initcap("first_name"))
df = df.withColumn("last_name", clean_string_initcap("last_name"))

# Email: regex validate then lowercase, NULL if invalid
email_regex = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
df = df.withColumn("email",
    F.when(
        F.upper(F.trim(F.col("email"))).isin(list(NULL_SENTINELS)),
        F.lit(None).cast(StringType())
    ).when(
        F.trim(F.col("email")).rlike(email_regex),
        F.lower(F.trim(F.col("email")))
    ).otherwise(F.lit(None).cast(StringType()))
)

# Gender: expand M/F
df = df.withColumn("gender", expand_gender("gender"))

# State: format_state
df = df.withColumn("state", format_state("state"))

# Strings: street_address, postal_code -> trim only
df = df.withColumn("street_address", clean_string_trim("street_address"))
df = df.withColumn("postal_code", clean_string_trim("postal_code"))

# Strings: city, country, traffic_source -> initcap
df = df.withColumn("city", clean_string_initcap("city"))
df = df.withColumn("country", clean_string_initcap("country"))
df = df.withColumn("traffic_source", clean_string_initcap("traffic_source"))

# Timestamps: created_at STRING -> TIMESTAMP (multi-format)
df = df.withColumn("created_at", parse_multi_format_timestamp("created_at"))

# Add silver_loaded_at timestamp
df = df.withColumn("silver_loaded_at", F.current_timestamp())

# ── Select final columns ──
df = df.select(
    "id",
    "first_name",
    "last_name",
    "email",
    "age",
    "gender",
    "state",
    "street_address",
    "postal_code",
    "city",
    "country",
    "latitude",
    "longitude",
    "traffic_source",
    "created_at",
    "silver_loaded_at"
)

# ── Write to silver ──
write_silver(df, "users")

# ── Export Iceberg metadata to BigLake Metastore ──
from google.cloud import bigquery
bq_client = bigquery.Client(project=PROJECT)
bq_client.query("EXPORT TABLE METADATA FROM `biglake-pipeline-test1.silver.users`").result()
""";
