COPY {{ table_name }} TO '{{ output_path }}' (HEADER, DELIMITER ',')
