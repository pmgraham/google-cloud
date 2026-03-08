UPDATE {{ table_name }}
SET "{{ column_name }}" = NULL
WHERE TRIM("{{ column_name }}") = ''
