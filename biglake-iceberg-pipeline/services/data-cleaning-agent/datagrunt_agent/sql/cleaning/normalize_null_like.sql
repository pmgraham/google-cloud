UPDATE {{ table_name }}
SET "{{ column_name }}" = NULL
WHERE LOWER(TRIM("{{ column_name }}"::VARCHAR)) IN ({{ sentinel_list }})
