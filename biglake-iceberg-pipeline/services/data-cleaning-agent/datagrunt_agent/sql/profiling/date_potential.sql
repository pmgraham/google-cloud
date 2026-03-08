SELECT COUNT(*) FROM {{ table_name }}
WHERE try_cast("{{ column_name }}" AS DATE) IS NOT NULL
  OR try_cast(try_strptime("{{ column_name }}"::VARCHAR, '%m/%d/%Y') AS DATE) IS NOT NULL
