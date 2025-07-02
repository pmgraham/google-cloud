"""Google Cloud Run Function remote function template for BigQuery. Gemini grounded in Google Search for medical device manufacturer lookup."""

# standard library imports
import base64
import json

# third party imports
import functions_framework
from google import genai
from google.genai import types

# Google Cloud setup variables
PROJECT = "my-google-cloud-project"
LOCATION = "global"
USE_VERTEX_AI = True

# Model variables
PROMPT = "find the medical device manufacturer for this: {bigquery_row_value}" # this variable is replaced with the actual value when passed into the function
MODEL = "gemini-2.5-flash" # starting with flash but can go to pro if needed; easy model updates in the future as needed
TEMPERATURE = 0.2 # set to 0.5 or lower for more factual output with less randomness to help avoid hallucinations
TOP_P = 1
SEED = 0
MAX_OUTPUT_TOKENS = 65535 # probably don't need this high for output but leaving for now b/c it's not going to hurt anything; change as desired

# Model function and output configuration
THINKING_BUDGET = -1
TOOLS = [types.Tool(google_search=types.GoogleSearch()),] # can change or add tools here for the model; grounded in Google Search for now

# Model safety configuration
SAFETY_SETTINGS = [
            types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="OFF"
        )
    ]


def generate(bigquery_row_value):
    """Calls Gemini based on a BigQuery value passed into the prompt."""
    
    client = genai.Client(
        vertexai=USE_VERTEX_AI,
        project=PROJECT,
        location=LOCATION,
    )

    prompt = PROMPT.format(bigquery_row_value=bigquery_row_value)
    message_text = types.Part.from_text(text=prompt)

    model = MODEL

    contents = [
      types.Content(
        role="user",
        parts=[
          message_text
        ]
      ),
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature = TEMPERATURE,
        top_p = TOP_P,
        seed = SEED,
        max_output_tokens = MAX_OUTPUT_TOKENS,
        safety_settings = SAFETY_SETTINGS,
        tools = TOOLS,
        thinking_config=types.ThinkingConfig(
        thinking_budget=THINKING_BUDGET,
        ),
    )

    response = "" # will append output from the for loop below
    for chunk in client.models.generate_content_stream(
        model = model,
        contents = contents,
        config = generate_content_config,
        ):
        if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
            continue
        response += chunk.text
    return response.replace('\n', '') # return the response and remove new line chars to keep the output clean in BigQuery


@functions_framework.http
def main(request):
    """
    A basic Cloud Function template for a BigQuery remote function.
    It receives data from BigQuery, processes each row, and returns a result.

    This function expects a single string argument from the BigQuery call.
    For example, in BigQuery: `my_remote_function(my_column)`
    """
    try:
        request_json = request.get_json(silent=True)
        calls = request_json['calls']
        replies = [None] * len(calls)  # Pre-allocate list for results to maintain order

        # Determine the number of workers (threads) to use.
        # This is an I/O-bound task (waiting for Gemini API responses).
        # Adjust `max_workers` based on testing, Gemini API rate limits,
        # and Cloud Run instance CPU/memory/concurrency.
        # Gemini 2.5 Flash has a default rate limit of 10 RPM (Requests Per Minute)
        # for free tier, and 1,000 RPM for paid tier per project.
        # Ensure max_workers aligns with your expected throughput and quotas.
        # A good starting point might be higher than vCPUs for I/O bound tasks.

        max_workers = 20 # Example: Adjust this value

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Store futures along with their original index
            future_to_index = {}
            for i, call in enumerate(calls):
                row_value = call[0]
                if isinstance(row_value, str):
                    future = executor.submit(generate, row_value)
                    future_to_index[future] = i
                else:
                    # Handle non-string inputs immediately
                    replies[i] = "ERROR: INPUT WAS NOT A STRING"

            # Process results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    processed_value = future.result()
                    replies[index] = processed_value
                except Exception as exc:
                    # Catch exceptions from the generate function itself
                    print(f"Error processing call at index {index}: {exc}")
                    replies[index] = f"ERROR: Processing failed - {str(exc)}"

        return json.dumps({"replies": replies})

    except Exception as e:
        # This catches errors in the main function's logic or unexpected issues
        print(f"Unhandled error in main function: {e}")
        return json.dumps({"errorMessage": str(e)}), 400
