CREATE TABLE `my-gcp-project.my-fuzzy-matching-dataset.customers_primary`
(
  customer_id INT64,
  full_name STRING,
  address STRING,
  email STRING
);

CREATE TABLE `my-gcp-project.my-fuzzy-matching-dataset.customers_secondary`
(
  record_id INT64,
  name STRING,
  street_address STRING,
  contact STRING
);

-- very small set of sample data to load into the tables created above.

INSERT INTO `my-gcp-project.my-fuzzy-matching-dataset.customers_primary` (customer_id, full_name, address, email)
VALUES
  (4, 'Samantha "Sam" Jones', '101 Maple Avenue, Greenfield, OH 45123', 'samantha.jones@example.com'),
  (2, 'Robert "Rob" Patterson', '456 Sunken Meadow Pkwy, Suite 3B, Meadowlands, NY 10001', 'rob.patterson@example.com'),
  (3, 'Jonathan Harker', '789 Carpathian Dr, Apt 12, Whitby, TX 78701', 'j.harker@example.com'),
  (5, 'William "Bill" Anderson', '212 Baker Street, London, WA 98004', 'bill.a@example.com'),
  (1, 'Dr. Eleanor Vance', '123 Shadow Creek Ln, Hill Dale, CA 90210', 'evance@example.com')
  ;

INSERT INTO `my-gcp-project.my-fuzzy-matching-dataset.customers_secondary` (record_id, name, street_address, contact)
VALUES
  (106, 'Bill Anderson', '212 Baker St, London, WA', 'contact@billing.com'),
  (103, 'Robbie Patterson', '456 Sunken Meadow Parkway, Ste 3B, Meadowlands NY', '555-123-4567'),
  (101, 'Eleanor Vance, PhD', '123 Shadow Creek Lane, Hill Dale, California', 'evance@email.com'),
  (102, 'Mr. Jonathan Harker', '789 Carpathian Drive #12, Whitby', 'jonathan.harker@email.com'),
  (104, 'Chris Peterson', '300 River Road, Riverside, CA 92501', 'chris.p@email.com'),
  (105, 'Sam Jones', '101 Maple Ave, Greenfield Ohio', 'samjones@email.com')
  ;
  
/*============================================================================================================================*/
CREATE OR REPLACE MODEL
  `my-gcp-project.my-models-dataset.customer_text_embedder` REMOTE
WITH CONNECTION `us.__default_cloudresource_connection__` -- <-- Replace with your actual connection ID
  OPTIONS ( endpoint = 'text-embedding-005' ); -- text-embedding-005 is the latest embeddings model as of now. replace as desired in the future.

/*============================================================================================================================*/

CREATE OR REPLACE TABLE `my-gcp-project.my-fuzzy-matching-dataset.customers_primary_embeddings` AS
SELECT
  -- Select all columns from the final result, except the temporary 'content' column
  -- and the status column, then rename the embedding result.
  * EXCEPT(content),
  content AS embeddings
FROM
  ML.GENERATE_TEXT_EMBEDDING(
    MODEL `my-gcp-project.my-models.customer_text_embedder`,
    (
      -- This subquery prepares the data for the model.
      -- It selects all original columns and creates a new 'content' column
      -- by concatenating the fields you want to embed.
      SELECT
        *,
        CONCAT(full_name, ",", address, ",", email) AS content
      FROM
        `my-gcp-project.my-fuzzy-matching-dataset.customers_primary` -- Corrected placeholder table name
    ),
    -- This option flattens the output JSON into an ARRAY<FLOAT64>
    STRUCT(TRUE AS flatten_json_output)
  );

/*============================================================================================================================*/

CREATE OR REPLACE TABLE `my-gcp-project.my-fuzzy-matching-dataset.customers_secondary_embeddings` AS
SELECT
  -- Select all columns from the final result, except the temporary 'content' column
  -- and the status column, then rename the embedding result.
  * EXCEPT(content),
  content AS embeddings
FROM
  ML.GENERATE_TEXT_EMBEDDING(
    MODEL `my-gcp-project.my-models.customer_text_embedder`,
    (
      -- This subquery prepares the data for the model.
      -- It selects all original columns and creates a new 'content' column
      -- by concatenating the fields you want to embed.
      SELECT
        *,
        CONCAT(name, ",", street_address, ",", contact) AS content
      FROM
        `my-gcp-project.my-fuzzy-matching-dataset.customers_secondary` -- Corrected placeholder table name
    ),
    -- This option flattens the output JSON into an ARRAY<FLOAT64>
    STRUCT(TRUE AS flatten_json_output)
  );

/*============================================================================================================================*/

-- This query finds the single closest match in the primary customers table
-- for each customer in the secondary customers table based on embedding similarity.

WITH best_match AS (
SELECT
    query.record_id AS secondary_id, -- ID from the query table
    base.customer_id AS primary_id, -- ID of the closest match from the base table
    query.name,
    base.full_name,
    query.street_address,
    base.address,
    query.contact,
    base.email,
    ROW_NUMBER() OVER(PARTITION BY base.customer_id ORDER BY distance ASC) AS row_num, -- window function to rank multiple matches based on distance
    -- query.text_embedding,
    -- base.text_embedding,
    distance -- The similarity score is returned by the function
FROM
    VECTOR_SEARCH(
        (SELECT customer_id, full_name, address, email, text_embedding FROM `my-gcp-project.my-fuzzy-matching-dataset.customers_primary_embeddings`), -- The base table to search within
        'text_embedding', -- Name of the embedding column in the base table
        (SELECT record_id, name, street_address, contact, text_embedding FROM `my-gcp-project.my-fuzzy-matching-dataset.customers_secondary_embeddings`), -- The table containing vectors to search for
        'text_embedding', -- Name of the embedding column in the query table
        top_k => 1,
        distance_type => 'COSINE'
    )
  )
-- when the CTE (WITH statement) above finds multiple matches for records, this query selects the best match based on distance
SELECT * EXCEPT(row_num)
FROM best_match
WHERE row_num = 1
