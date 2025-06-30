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
        # The request from BigQuery is a JSON object. We need to parse it.
        # The `silent=True` argument prevents an error if the request body is not JSON.
        request_json = request.get_json(silent=True)

        # BigQuery batches rows into a "calls" field in the JSON payload.
        # "calls" is a list of lists. Each inner list represents the arguments for one row.
        # e.g., {"calls": [["value from row 1"], ["value from row 2"]]}
        calls = request_json['calls']

        # We will collect our results in this list.
        replies = []

        # Loop through each "call" from BigQuery. Each "call" corresponds to one row.
        for call in calls:
            # -----------------------------------------------------------------
            # THIS IS WHERE YOU ACCESS THE VALUE FROM THE BIGQUERY ROW.
            # `call` is a list of arguments from your BigQuery function call.
            # `call[0]` is the first argument, `call[1]` is the second, and so on.
            # For a function call like `my_remote_function(my_column)`,
            # `row_value` will hold the value of `my_column` for the current row.
            row_value = call[0]
            # -----------------------------------------------------------------


            # --- YOUR CUSTOM LOGIC GOES HERE ---
            #
            # For this basic example, we will just process the input string.
            # You would replace this section with your own code, like calling an external API.
            #
            if isinstance(row_value, str):
                # Example: Convert the text to uppercase.
                processed_value = generate(row_value) # calling the function from above
            else:
                # It's good practice to handle non-string inputs.
                processed_value = "ERROR: INPUT WAS NOT A STRING"

            # Add the processed value to our list of replies.
            replies.append(processed_value)

        # The function must return a JSON object with a single key, "replies".
        # The "replies" list must contain one response for each call in the original request.
        return json.dumps({"replies": replies})

    except Exception as e:
        # If an error occurs, return it in a format BigQuery understands.
        return json.dumps({"errorMessage": str(e)}), 400
