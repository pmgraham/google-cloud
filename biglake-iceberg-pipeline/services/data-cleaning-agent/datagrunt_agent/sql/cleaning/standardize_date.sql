UPDATE {{ table_name }}
SET "{{ column_name }}" = STRFTIME(TRY_CAST("{{ column_name }}" AS DATE), '%Y-%m-%d')
WHERE TRY_CAST("{{ column_name }}" AS DATE) IS NOT NULL
