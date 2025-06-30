DECLARE gemini_prompt STRING;

SET gemini_prompt = 'Evaluate the responses and identify the primary medical device kit manufacturer for the following text. Return the result as a JSON object with "manufacturer" as the key and the extracted manufactueres as a JSON array. Even if only one manufacturer is found make sure to return the value as an array.';

/*  You will also have to setup a BigQuery external connection to support the remote function. Once you create the connection, you will have to give the connection's
    service account the correct permissions. It will need at least Cloud Run Invoker, Cloud Run Functions Invoker, and Vertex AI User roles in IAM.
*/
--================================================================================================================================================================================
# Create the User Defined Function (UDF) that will call the Google Cloud Function
CREATE OR REPLACE FUNCTION `my-google-cloud-project.single-region-dataset.remote-function-name`(prompt STRING)
RETURNS STRING
REMOTE WITH CONNECTION `my-google-cloud-project.us-central1.remote-functions`
OPTIONS (
  endpoint = "cloud-run-function-url"
);
--================================================================================================================================================================================
# Execute the UDF function call and store the results to a table
CREATE OR REPLACE TABLE `my-google-cloud-project.single-region-dataset.output-results-table` AS
SELECT
  kit,
  kit_part,
  pri_product_desc,
  prompt_string,
  `my-google-cloud-project.single-region-dataset.remote-function-name`(prompt_string) AS gemini_response
FROM `my-google-cloud-project.single-region-dataset.medical_device_kits`;
--================================================================================================================================================================================
# Create the local Gemini model needed for entity extraction in the next steps
CREATE OR REPLACE MODEL `my-google-cloud-project.single-region-models-dataset.gemini-bigquery-model-name`
  REMOTE WITH CONNECTION `my-google-cloud-project.us-central1.remote-functions`
  OPTIONS (
    endpoint = 'gemini-2.5-pro' --can be any supported gemini model
  );
--================================================================================================================================================================================
# Perform entity extraction utilizing BigQuery ML using Gemini to parse the response from the remote function call
WITH cleanup AS (
    SELECT
      kit,
      kit_part,
      pri_product_desc,
      gemini_response,
      ml_generate_text_llm_result,
      REGEXP_REPLACE(ml_generate_text_llm_result, r'^```json\s*|\s*```$', '') AS manufacturers_extracted
    FROM
      ML.GENERATE_TEXT(
        MODEL `my-google-cloud-project.single-region-models-dataset.gemini-bigquery-model-name`,
        (
          SELECT
            kit,
            kit_part,
            pri_product_desc,
            gemini_response,
            CONCAT(
              gemini_prompt, -- this is the variable set at the top of the SQL script
              gemini_response
            ) AS prompt,
          FROM
            `my-google-cloud-project.single-region-dataset.output-results-table`
        ),
        STRUCT(
          0.2 AS temperature,
          8192 AS max_output_tokens,
          TRUE AS flatten_json_output
        )
      )
  )
SELECT
  kit,
  kit_part,
  pri_product_desc,
  gemini_response,
  ml_generate_text_llm_result,
  manufacturers_extracted,
  (
    SELECT
      STRING_AGG(JSON_VALUE(manufacturer, '$'), '|')
    FROM
      UNNEST(JSON_QUERY_ARRAY(manufacturers_extracted, '$.manufacturer')) AS manufacturer
  ) AS manufacturers_pipe_separated
FROM cleanup;
--================================================================================================================================================================================
