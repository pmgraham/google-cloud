ALTER TABLE {{ table_name }}
ALTER COLUMN "{{ column_name }}" SET DATA TYPE {{ new_type }}
USING TRY_CAST("{{ column_name }}" AS {{ new_type }})
