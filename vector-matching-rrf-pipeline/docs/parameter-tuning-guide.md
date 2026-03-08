# Pipeline Parameter Tuning Guide

This pipeline utilizes mathematical heuristics and AI confidence bounds to evaluate matches. 

## 🚨 Edit Parameters Here: `config/customer_schema.json` 🚨
**All of the following parameters are fully externalized in this single JSON file!** Do not edit the `.sql` templates directly.

Adjusting these values directly impacts the performance of the matching engine. When tuning the system, you are generally trading off between two core evaluation metrics:
- **Precision (Accuracy of Matches)**: Of all the matches the pipeline *claimed* were correct, what percentage of them were *actually* true matches? High precision means very few "False Positives" (bad matches). **Important: Because this pipeline evaluates *distance* between items, a LOWER numerical score (e.g., 0.05) represents a highly PRECISE, tight match. A HIGHER numerical score (e.g., 0.85) represents a LOOSE, low-precision match.** To achieve higher precision across your dataset, you must set a STRICTER (lower) threshold cutoff.
- **Recall (Coverage of Matches)**: Of all the true matches that *actually exist* in your databases, what percentage did the pipeline successfully *find*? High recall means very few "False Negatives" (missed matches). To achieve higher recall, you must set a LOOSER (higher) threshold cutoff, allowing the pipeline to catch matches even if they are slightly messy or unclear.

## AI Generation Parameters

### `llm_temperature`
- **Default:** `0.0`
- **What it does:** Controls the randomness/creativity of the Gemini text model when extracting JSON attributes like `size_value` and `part_type` from the raw descriptions.
- **Why adjust it:** 
  - Keep at `0.0` for **maximum determinism** (the model gives the same answer every time).
  - You would rarely raise this for data extraction tasks. If the model is failing to identify fields, tune `config/prompt.txt` instead of raising temperature.

### `llm_max_output_tokens`
- **Default:** `8192`
- **What it does:** The absolute maximum length of the JSON response the LLM is allowed to generate.
- **Why adjust it:** 
  - If you add many new fields to your expected JSON schema and the LLM's response starts getting cut off mid-string, increase this value.
  - Decrease it to strictly enforce short outputs and error out if the model begins hallucinating massive strings.

## Vector Search Parameters

### `vector_search_top_k`
- **Default:** `100`
- **What it does:** Determines how many "nearest neighbor" candidate embeddings BigQuery retrieves per customer part before applying lexical (text) scoring and RRF.
- **Why adjust it:** 
  - **Increase (e.g., 200, 500):** Try this if **Recall is low**. By grabbing a wider net of semantic candidates, you increase the chance that the true match is somewhere in the pile. (Costs more compute).
  - **Decrease (e.g., 50, 10):** Try this if you want maximum speed and the dataset is clean enough that the semantic vector search almost always places the true match right at the top.

## Reciprocal Rank Fusion (RRF) Parameters

RRF is a mathematical formula that combines the numerical rank of the Semantic Vector distance and the Lexical Edit distance. The formula is: `(1.0 / (vector_rank + rrf_constant)) + (1.0 / (lexical_rank + rrf_constant))`

### `rrf_constant`
- **Default:** `60`
- **What it does:** The dampening parameter "k" in the standard industry RRF algorithm. 
- **Why adjust it:** 
  - `60` is the industry standard baseline for search retrieval. 
  - **Decrease (e.g., 10, 20):** Heavily penalizes items that aren't at the absolute top of the individual ranks. The score drops off much harder for rank #5 vs rank #1.
  - **Increase (e.g., 100):** Flattens the curve. Rank #1 and Rank #10 are treated much more similarly.

### `match_rrf_auto_approve_threshold`
- **Default:** `0.031`
- **What it does:** The strict upper bound threshold. Any candidate scoring above this is considered a "Slam Dunk" and is automatically piped into the `auto_approved_matches` table, bypassing the AI agent entirely.

### `match_rrf_agent_review_threshold`
- **Default:** `0.025`
- **What it does:** The lower bound threshold for edge-cases. Candidates scoring between this and the `auto_approve` threshold are piped into the `agent_review_queue` for manual evaluation by the autonomous ADK agent.
- **Why adjust it:** 
  - **Increase (e.g., 0.028):** Use this to aggressively filter out **False Positives** from even reaching the agent, saving Vertex API costs but increasing the number of parts left totally unmatched.
  - **Decrease (e.g., 0.020):** Use this to improve **Recall**. If the pipeline is failing to match parts because the lexical string is visually messy, lowering the cutoff allows looser edge-case matches to be routed to the agent for investigation.

## Evaluation Parameters

### `eval_rrf_threshold`
- **Default:** `0.015`
- **What it does:** Similar to `match_rrf_threshold`, but used internally during the evaluation script to calculate hypothetical total prediction counts across the entire truth table grid.
- **Why adjust it:** 
  - Generally, you keep this slightly looser than the `match_rrf_threshold` to see what candidates were "just below the cutoff" during your evaluation analysis.
