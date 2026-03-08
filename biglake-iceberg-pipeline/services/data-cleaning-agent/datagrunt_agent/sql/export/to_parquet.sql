COPY {{ table_name }} TO '{{ output_path }}' (FORMAT PARQUET)
