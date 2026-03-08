UPDATE {{ table_name }}
SET "{{ column_name }}" = LOWER("{{ column_name }}")
WHERE "{{ column_name }}" IS NOT NULL
