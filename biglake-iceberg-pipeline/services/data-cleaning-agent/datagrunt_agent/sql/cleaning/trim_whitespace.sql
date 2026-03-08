UPDATE {{ table_name }}
SET "{{ column_name }}" = TRIM("{{ column_name }}")
WHERE "{{ column_name }}" IS NOT NULL
  AND "{{ column_name }}" != TRIM("{{ column_name }}")
