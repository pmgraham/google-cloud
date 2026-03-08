COPY (SELECT * FROM {{ table_name }}) TO '{{ output_path }}' (ARRAY true)
