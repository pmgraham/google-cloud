UPDATE {{ table_name }}
SET "{{ column_name }}" = REPLACE("{{ column_name }}", '�', '')
WHERE "{{ column_name }}" LIKE '%�%'
