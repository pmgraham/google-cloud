#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/pipeline.env"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: pipeline.env not found."
    echo "  cp pipeline.env.example pipeline.env"
    echo "  # Edit pipeline.env with your values"
    echo "  ./setup.sh"
    exit 1
fi

# Source the config
source "${ENV_FILE}"

# Validate required variables
for var in PROJECT_ID INBOX_BUCKET_NAME STAGING_BUCKET_NAME ICEBERG_BUCKET_NAME ARCHIVE_BUCKET_NAME BQ_LOCATION BIGLAKE_CONNECTION SPARK_CONNECTION; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: ${var} is not set in pipeline.env"
        exit 1
    fi
done

echo "Configuring SQL templates..."
echo "  PROJECT_ID:           ${PROJECT_ID}"
echo "  ICEBERG_BUCKET_NAME:  ${ICEBERG_BUCKET_NAME}"
echo "  BQ_LOCATION:          ${BQ_LOCATION}"
echo "  BIGLAKE_CONNECTION:   ${BIGLAKE_CONNECTION}"
echo "  SPARK_CONNECTION:     ${SPARK_CONNECTION}"
echo ""

# Cross-platform sed -i
if [[ "$(uname)" == "Darwin" ]]; then
    SED_INPLACE=(-i '')
else
    SED_INPLACE=(-i)
fi

# Find all SQL files under test_data/ and test_sql/
count=0
while IFS= read -r -d '' file; do
    sed "${SED_INPLACE[@]}" \
        -e "s/__PROJECT_ID__/${PROJECT_ID}/g" \
        -e "s/__ICEBERG_BUCKET_NAME__/${ICEBERG_BUCKET_NAME}/g" \
        -e "s/__REGION__/${BQ_LOCATION}/g" \
        -e "s/__BIGLAKE_CONNECTION__/${BIGLAKE_CONNECTION}/g" \
        -e "s/__SPARK_CONNECTION__/${SPARK_CONNECTION}/g" \
        "${file}"
    count=$((count + 1))
done < <(find "${SCRIPT_DIR}/test_data" "${SCRIPT_DIR}/test_sql" -name "*.sql" -type f -print0)

echo "Updated ${count} SQL files."
echo ""
echo "Done! Next steps:"
echo "  1. cd terraform && terraform init && terraform apply"
echo "  2. ./deploy.sh                     # deploy Cloud Run services"
echo "  3. python test_data/thelook_ecommerce/seed.py   # seed bronze tables"
