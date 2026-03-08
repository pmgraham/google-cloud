SELECT COUNT(*) FROM {{ table_name }}
WHERE try_cast(regexp_replace("{{ column_name }}"::VARCHAR, '[\$\%\,]', '', 'g') AS DOUBLE) IS NOT NULL
  AND "{{ column_name }}" IS NOT NULL
