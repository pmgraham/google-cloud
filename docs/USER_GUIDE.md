# User Guide

This guide helps analysts and business users get the most out of the Data Insights Agent. The application lets you explore BigQuery data using plain English questions -- no SQL knowledge required.

## Getting Started

When you open the application, you'll see a chat interface with an empty message area and a text input at the bottom. The agent will greet you with a welcome message and a few starter suggestions you can click to get started.

### Your First Query

Type a question in the input field and press **Enter** (or click the send button). Examples of good first questions:

- "What tables are available?"
- "Show me recent data trends"
- "What are the top performing items?"

The agent will interpret your question, query the database, and return results in seconds.

## Writing Effective Queries

### Be Specific

The more specific your question, the better the results. Compare:

| Vague | Specific |
|-------|----------|
| "Show me data" | "Show me sales by state for the last month" |
| "What happened?" | "What were the top 10 products by revenue last quarter?" |
| "Any trends?" | "How has monthly revenue changed over the past year?" |

### Types of Questions You Can Ask

**Exploration queries** -- discover what data is available:
- "What tables are available?"
- "What columns does the orders table have?"
- "Show me a sample of the customers table"

**Aggregation queries** -- summarize data:
- "What are total sales by region?"
- "How many orders were placed each month?"
- "What's the average order value by customer segment?"

**Filtering queries** -- narrow down results:
- "Show me stores in California"
- "Which products had more than 100 orders?"
- "What orders were placed in the last 7 days?"

**Ranking queries** -- find top/bottom performers:
- "What are the top 10 products by revenue?"
- "Which states have the fewest stores?"
- "Show me the 5 lowest-performing regions"

**Trend queries** -- analyze changes over time:
- "How has revenue changed month over month?"
- "Show me daily order counts for the past 30 days"
- "Compare this quarter's sales to last quarter"

### Clarifying Questions

If your question is ambiguous, the agent will ask for clarification. For example, if you ask "show me the data," the agent might respond with:

> Which table should I query?
> - orders
> - customers
> - products

Click one of the options to continue, or type your own answer.

## Working with Results

### Viewing Query Results

When the agent runs a query, you'll see a **"View results"** button in the chat message showing how many rows were returned. Click it to open the results panel on the right side of the screen.

### Data Table

The default view shows your results in an interactive table with:

- **Sorting**: Click any column header to sort ascending or descending
- **Pagination**: Navigate through results 10 rows at a time using the page controls at the bottom
- **Row count**: See which rows you're viewing and the total count (e.g., "Showing 1-10 of 50 rows")

Number values are automatically formatted with thousands separators for readability.

### Charts

Switch between different visualizations using the chart type buttons above the results:

| Chart Type | Best For |
|------------|----------|
| **Table** | Detailed data inspection, all data types |
| **Bar** | Comparing categories (e.g., sales by state) |
| **Line** | Time series and trends (e.g., revenue over months) |
| **Area** | Cumulative trends with volume emphasis |
| **Pie** | Parts of a whole (e.g., market share distribution) |

When multiple numeric columns are available, use the **Metric** dropdown to choose which column to visualize on the y-axis.

Charts are interactive -- hover over data points to see exact values in tooltips.

### Exporting Data

Click the **Export** button (download icon) in the results panel header to download your query results as a CSV file. The file is named with the current date (e.g., `query_results_2025-01-15.csv`).

Enriched and calculated values are exported as their plain values (without metadata).

### Viewing the SQL Query

At the bottom of the results panel, you can see the exact SQL query that was executed, along with the query execution time. This is useful for understanding what the agent did and for debugging.

## Data Enrichment

Enrichment lets you augment your query results with real-time information from Google Search -- data that doesn't exist in your database.

### When to Use Enrichment

Use enrichment when you want to add external context to your results. For example:

- You have a list of states and want to add their capitals or populations
- You have company names and want to add their founding year or CEO
- You have cities and want to add notable landmarks or events

### How to Request Enrichment

After running a query, ask the agent to add information. Examples:

- "Add state capitals to this data"
- "Enrich the results with population data for each state"
- "Include the founding year for each company"

The agent will confirm what it can add and proceed with the enrichment.

### Understanding Enriched Data

Enriched columns appear in the table with special styling:

- **Purple columns**: Data sourced from Google Search
- **Hover tooltips**: Hover over any enriched cell to see:
  - **Source**: Where the data came from (e.g., "Wikipedia: California")
  - **Confidence**: How reliable the data is (high, medium, or low)
  - **Freshness**: How current the data is (static, current, dated, or stale)
  - **Warnings**: Any data quality concerns

A purple **"Enriched Data"** banner appears above the results showing:
- How many values were enriched
- Which fields were added
- Any warnings about failed lookups

### Enrichment Limits

- Maximum **20 unique values** can be enriched per request
- Maximum **5 fields** can be added per value
- Some lookups may fail if Google Search can't find reliable data for a value

### Important Notes About Enriched Data

- Enriched data comes from web search results, not your database
- Dynamic data (like population or leaders) may vary by source or time
- Always check the source attribution before making decisions based on enriched data
- If some enrichments fail, the agent will show warnings for the missing values

## Calculated Columns

Calculated columns let you derive new values from existing data without re-running the database query.

### When to Use Calculated Columns

After you have query results (with or without enrichment), ask for derived calculations:

- "Add residents per store" (after enriching with population)
- "Calculate profit margin as a percentage"
- "What's the revenue per customer?"

### How to Request Calculations

Simply ask in natural language:

- "Add a column showing revenue per customer"
- "Calculate the profit margin as (revenue - costs) / revenue * 100"
- "Show me residents per store using the population data"

### Understanding Calculated Data

Calculated columns appear with:

- **Blue columns**: Data derived from mathematical expressions
- **Hover tooltips**: Hover over cells to see:
  - **Formula**: The expression used (e.g., `_enriched_population / store_count`)
  - **Format**: How the value is displayed (number, integer, percent, or currency)
  - **Warnings**: Any calculation errors (e.g., division by zero)

A blue **"Calculated Columns"** banner shows the formulas used.

### Format Types

Calculated values are formatted based on their type:

| Format | Display Example | Use Case |
|--------|----------------|----------|
| Number | 1,234.56 | General numeric values |
| Integer | 1,235 | Whole numbers, counts |
| Percent | 45.2% | Percentages, ratios |
| Currency | $1,234.56 | Money values |

## Conversation Context

The agent remembers your conversation within a session. You can ask follow-up questions that reference previous results:

1. "Show me stores by state" -- initial query
2. "Add population data" -- enriches the previous result
3. "Calculate residents per store" -- adds a calculated column
4. "Now show me just the top 5 by that metric" -- refines the analysis

### Starting a New Conversation

Click the **New Chat** button in the header to clear the conversation and start fresh. This creates a new session with no prior context.

## AI-Generated Insights

After running queries, the agent may provide proactive insights displayed as colored badges:

| Badge Color | Type | Meaning |
|-------------|------|---------|
| Blue | Trend | Directional changes over time |
| Amber | Anomaly | Unusual values or patterns |
| Purple | Comparison | Relative performance context |
| Green | Suggestion | Recommendations for further analysis |

These insights are generated automatically -- you don't need to ask for them.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Enter** | Send message |
| **Shift+Enter** | New line in message |

## Tips for Best Results

1. **Start broad, then narrow down**: Begin with "What tables are available?" to understand your data before diving into specific queries.

2. **Use follow-up questions**: Build on previous results instead of starting over. The agent remembers context within a session.

3. **Ask for enrichment after initial queries**: Run your base query first, then ask to enrich with external data.

4. **Use calculated columns for derived metrics**: Instead of asking for a new query, request calculations on existing results.

5. **Check enrichment sources**: Always verify the source and confidence of enriched data before making decisions.

6. **Export for further analysis**: Use the CSV export to work with results in spreadsheet applications.

## Troubleshooting

**The agent says it can't find a table**
- Ask "What tables are available?" to see what data exists
- Check that you're using the correct table name

**Query results seem wrong**
- Check the SQL query shown at the bottom of the results panel
- Rephrase your question with more specific criteria

**Enrichment failed for some values**
- Check the warnings in the enrichment banner
- Some values may not have reliable data available via web search
- Try enriching with different fields

**The agent asks too many clarifying questions**
- Be more specific in your initial question
- Include the table name, time range, and desired metrics upfront
