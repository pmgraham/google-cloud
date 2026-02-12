/**
 * Role of a message in the chat conversation.
 *
 * @remarks
 * Used to distinguish between different participants in the chat interface:
 * - `user`: Messages sent by the end user
 * - `assistant`: Messages sent by the AI agent
 * - `system`: System-generated messages (errors, notifications)
 *
 * @example
 * ```typescript
 * const userMessage: ChatMessage = {
 *   id: "msg-123",
 *   role: "user",
 *   content: "Show me sales by state",
 *   // ...
 * };
 * ```
 */
export type MessageRole = 'user' | 'assistant' | 'system';

/**
 * Available chart visualization types for query results.
 *
 * @remarks
 * The chart type determines how data is displayed in the Results panel.
 * Chart type selection is automatic based on data shape, but users can
 * override via the chart selector UI.
 *
 * Chart type guidelines:
 * - `table`: Always available, default view
 * - `bar`: Best for categorical comparisons (e.g., sales by state)
 * - `line`: Best for time series data
 * - `pie`: Best for showing parts of a whole (max 10 categories)
 * - `area`: Best for cumulative trends over time
 *
 * @example
 * ```typescript
 * const chartType: ChartType = "bar";
 * const config = generateChartConfig(queryResult, chartType);
 * ```
 */
export type ChartType = 'table' | 'bar' | 'line' | 'pie' | 'area';

/**
 * Schema information for a single column in query results.
 *
 * @remarks
 * Describes the structure and metadata of a data column returned from BigQuery.
 * Includes flags to identify enriched and calculated columns, which require
 * special handling for data extraction and display.
 *
 * @example
 * ```typescript
 * // Regular column from database
 * const regularColumn: ColumnInfo = {
 *   name: "state",
 *   type: "STRING",
 * };
 *
 * // Enriched column (added via apply_enrichment)
 * const enrichedColumn: ColumnInfo = {
 *   name: "_enriched_capital",
 *   type: "STRING",
 *   is_enriched: true,
 * };
 *
 * // Calculated column (added via add_calculated_column)
 * const calculatedColumn: ColumnInfo = {
 *   name: "residents_per_store",
 *   type: "FLOAT64",
 *   is_calculated: true,
 * };
 * ```
 */
export interface ColumnInfo {
  /** Column name as it appears in the data (enriched columns prefixed with `_enriched_`) */
  name: string;
  /** BigQuery data type (STRING, INTEGER, FLOAT64, BOOLEAN, etc.) */
  type: string;
  /** True if this column was added via apply_enrichment() tool */
  is_enriched?: boolean;
  /** True if this column was added via add_calculated_column() tool */
  is_calculated?: boolean;
}

/**
 * Value object for enriched data columns with metadata and source attribution.
 *
 * @remarks
 * When the AI agent enriches query results with real-time data from Google Search,
 * enriched column values are objects (not primitives) that include the actual value
 * plus metadata about the data source, confidence level, and freshness.
 *
 * **Important**: When extracting numeric values for charts, use the `extractNumericValue()`
 * helper function to handle both primitive values and enriched value objects.
 *
 * **Confidence Levels**:
 * - `high`: Value found in authoritative sources (e.g., government sites, Wikipedia)
 * - `medium`: Value found in reputable sources but may vary
 * - `low`: Value found but source is uncertain or conflicting
 * - `null`: No confidence data available
 *
 * **Freshness Indicators**:
 * - `static`: Historical data that doesn't change (e.g., "Year California joined union")
 * - `current`: Recently updated data (e.g., "Current population")
 * - `dated`: Data from a past time period (e.g., "2020 census data")
 * - `stale`: Data is old and may be outdated
 * - `null`: No freshness data available
 *
 * @example
 * ```typescript
 * // Enriched state capital (static data, high confidence)
 * const capital: EnrichedValue = {
 *   value: "Sacramento",
 *   source: "Wikipedia: California",
 *   confidence: "high",
 *   freshness: "static",
 *   warning: null
 * };
 *
 * // Enriched population (current data with warning)
 * const population: EnrichedValue = {
 *   value: 39500000,
 *   source: "U.S. Census Bureau (2023)",
 *   confidence: "high",
 *   freshness: "current",
 *   warning: "Estimated value, may vary by source"
 * };
 *
 * // Failed enrichment
 * const failed: EnrichedValue = {
 *   value: null,
 *   source: null,
 *   confidence: null,
 *   freshness: null,
 *   warning: "No enrichment data found for 'PR'"
 * };
 *
 * // Extracting for charts (use helper function)
 * import { extractNumericValue } from '../utils/chartHelpers';
 * const numericValue = extractNumericValue(population); // Returns 39500000
 * ```
 */
export interface EnrichedValue {
  /** The actual enriched value (can be string, number, or null if enrichment failed) */
  value: unknown;
  /** Attribution for where this data came from (e.g., "Wikipedia: California") */
  source: string | null;
  /** Reliability level of the enriched data */
  confidence: 'high' | 'medium' | 'low' | null;
  /** How current or static the data is */
  freshness: 'static' | 'current' | 'dated' | 'stale' | null;
  /** Error message if enrichment failed or data quality concern */
  warning: string | null;
}

/**
 * Value object for calculated columns created from expressions.
 *
 * @remarks
 * When the AI agent adds calculated columns using the `add_calculated_column()` tool,
 * each calculated value is an object containing the computed result plus metadata
 * about how it was calculated.
 *
 * Calculated columns allow deriving new values from existing data without re-running
 * the database query. This is especially useful for combining base data with enriched data.
 *
 * **Format Types**:
 * - `number`: Default, rounds to 2 decimal places (e.g., 3.14)
 * - `integer`: Whole numbers only (e.g., 42)
 * - `percent`: Percentage values (e.g., 23.5%)
 * - `currency`: Money values (e.g., $1,234.56)
 *
 * **Important**: Like enriched values, calculated values are objects, not primitives.
 * Use `extractNumericValue()` when preparing data for charts.
 *
 * @example
 * ```typescript
 * // Residents per store calculation (integer format)
 * const residentsPerStore: CalculatedValue = {
 *   value: 5234,
 *   expression: "_enriched_population / store_count",
 *   format_type: "integer",
 *   is_calculated: true
 * };
 *
 * // Profit margin calculation (percent format)
 * const profitMargin: CalculatedValue = {
 *   value: 23.5,
 *   expression: "(revenue - costs) / revenue * 100",
 *   format_type: "percent",
 *   is_calculated: true
 * };
 *
 * // Failed calculation (division by zero)
 * const failed: CalculatedValue = {
 *   value: null,
 *   expression: "revenue / customer_count",
 *   format_type: "number",
 *   is_calculated: true,
 *   warning: "Division by zero in row 3"
 * };
 *
 * // Extracting for charts (use helper function)
 * import { extractNumericValue } from '../utils/chartHelpers';
 * const numericValue = extractNumericValue(profitMargin); // Returns 23.5
 * ```
 */
export interface CalculatedValue {
  /** The computed numeric result (null if calculation failed) */
  value: number | null;
  /** The mathematical expression used to calculate this value */
  expression: string;
  /** Display format hint for rendering the value */
  format_type: 'number' | 'integer' | 'percent' | 'currency';
  /** Always true for calculated values (type discriminator) */
  is_calculated: true;
  /** Error message if calculation failed (e.g., division by zero) */
  warning?: string;
}

/**
 * Metadata about enrichment operations applied to query results.
 *
 * @remarks
 * When the AI agent enriches query results via the `apply_enrichment()` tool,
 * this metadata tracks which columns were enriched, how many values succeeded,
 * and any warnings about failed enrichments.
 *
 * The frontend uses this to display enrichment badges and warning messages.
 *
 * @example
 * ```typescript
 * // Successful full enrichment
 * const enrichmentMeta: EnrichmentMetadata = {
 *   source_column: "state",
 *   enriched_fields: ["capital", "population"],
 *   total_enriched: 50,
 *   warnings: [],
 *   partial_failure: false
 * };
 *
 * // Partial enrichment with warnings
 * const partialMeta: EnrichmentMetadata = {
 *   source_column: "state",
 *   enriched_fields: ["capital", "governor"],
 *   total_enriched: 48,
 *   warnings: [
 *     "No enrichment data found for 'PR'",
 *     "No enrichment data found for 'GU'"
 *   ],
 *   partial_failure: true
 * };
 * ```
 */
export interface EnrichmentMetadata {
  /** Name of the column that was enriched (e.g., "state", "city") */
  source_column: string;
  /** List of field names that were added (without `_enriched_` prefix) */
  enriched_fields: string[];
  /** Number of unique values that were successfully enriched */
  total_enriched: number;
  /** List of warnings about failed enrichments (limited to first 5) */
  warnings: string[];
  /** True if any enrichments failed */
  partial_failure: boolean;
}

/**
 * Information about a single calculated column.
 *
 * @remarks
 * Describes a column that was added via the `add_calculated_column()` tool,
 * including the expression used to compute values and the display format.
 *
 * @example
 * ```typescript
 * const columnInfo: CalculatedColumnInfo = {
 *   name: "residents_per_store",
 *   expression: "_enriched_population / store_count",
 *   format_type: "integer"
 * };
 * ```
 */
export interface CalculatedColumnInfo {
  /** Name of the calculated column */
  name: string;
  /** Mathematical expression used to calculate values */
  expression: string;
  /** Display format hint (number, integer, percent, currency) */
  format_type: string;
}

/**
 * Metadata about calculation operations applied to query results.
 *
 * @remarks
 * When the AI agent adds calculated columns via the `add_calculated_column()` tool,
 * this metadata tracks which columns were added and any calculation errors.
 *
 * @example
 * ```typescript
 * // Successful calculation
 * const calcMeta: CalculationMetadata = {
 *   calculated_columns: [
 *     {
 *       name: "profit_margin",
 *       expression: "(revenue - costs) / revenue * 100",
 *       format_type: "percent"
 *     }
 *   ],
 *   warnings: []
 * };
 *
 * // Calculation with errors
 * const errorMeta: CalculationMetadata = {
 *   calculated_columns: [
 *     {
 *       name: "avg_revenue_per_customer",
 *       expression: "revenue / customer_count",
 *       format_type: "currency"
 *     }
 *   ],
 *   warnings: [
 *     "Row 3: Division by zero",
 *     "Row 7: Invalid expression"
 *   ]
 * };
 * ```
 */
export interface CalculationMetadata {
  /** List of calculated columns that were added */
  calculated_columns: CalculatedColumnInfo[];
  /** List of calculation errors (limited to first 5 rows) */
  warnings: string[];
}

/**
 * Results from a SQL query execution with optional enrichment and calculation metadata.
 *
 * @remarks
 * This is the **primary data structure** returned from the backend `/api/chat` endpoint
 * when the AI agent executes a BigQuery query. It contains the query results plus
 * metadata about enrichment and calculation operations.
 *
 * **Row Value Types**:
 * The `rows` array contains objects where values can be:
 * - **Primitives** (string, number, boolean, null): Regular database columns
 * - **EnrichedValue objects**: Columns added via `apply_enrichment()`
 * - **CalculatedValue objects**: Columns added via `add_calculated_column()`
 *
 * When processing row data for charts, use `extractNumericValue()` to handle
 * all three value types correctly.
 *
 * **Enrichment & Calculation Workflow**:
 * 1. Agent executes base query → Returns QueryResult with base data
 * 2. User requests enrichment → Returns QueryResult with enrichment_metadata
 * 3. User requests calculations → Returns QueryResult with calculation_metadata
 *
 * @example
 * ```typescript
 * // Base query result (no enrichment or calculations)
 * const baseResult: QueryResult = {
 *   columns: [
 *     { name: "state", type: "STRING" },
 *     { name: "store_count", type: "INTEGER" }
 *   ],
 *   rows: [
 *     { state: "CA", store_count: 150 },
 *     { state: "TX", store_count: 120 }
 *   ],
 *   total_rows: 2,
 *   query_time_ms: 234.56,
 *   sql: "SELECT state, COUNT(*) as store_count FROM stores GROUP BY state"
 * };
 *
 * // Enriched query result
 * const enrichedResult: QueryResult = {
 *   columns: [
 *     { name: "state", type: "STRING" },
 *     { name: "store_count", type: "INTEGER" },
 *     { name: "_enriched_capital", type: "STRING", is_enriched: true }
 *   ],
 *   rows: [
 *     {
 *       state: "CA",
 *       store_count: 150,
 *       _enriched_capital: {
 *         value: "Sacramento",
 *         source: "Wikipedia: California",
 *         confidence: "high",
 *         freshness: "static",
 *         warning: null
 *       }
 *     }
 *   ],
 *   total_rows: 1,
 *   query_time_ms: 234.56,
 *   sql: "SELECT state, COUNT(*) as store_count FROM stores GROUP BY state",
 *   enrichment_metadata: {
 *     source_column: "state",
 *     enriched_fields: ["capital"],
 *     total_enriched: 1,
 *     warnings: [],
 *     partial_failure: false
 *   }
 * };
 *
 * // Query with both enrichment and calculations
 * const fullResult: QueryResult = {
 *   columns: [
 *     { name: "state", type: "STRING" },
 *     { name: "store_count", type: "INTEGER" },
 *     { name: "_enriched_population", type: "INTEGER", is_enriched: true },
 *     { name: "residents_per_store", type: "INTEGER", is_calculated: true }
 *   ],
 *   rows: [
 *     {
 *       state: "CA",
 *       store_count: 150,
 *       _enriched_population: {
 *         value: 39500000,
 *         source: "U.S. Census (2023)",
 *         confidence: "high",
 *         freshness: "current",
 *         warning: null
 *       },
 *       residents_per_store: {
 *         value: 263333,
 *         expression: "_enriched_population / store_count",
 *         format_type: "integer",
 *         is_calculated: true
 *       }
 *     }
 *   ],
 *   total_rows: 1,
 *   query_time_ms: 234.56,
 *   sql: "SELECT state, COUNT(*) as store_count FROM stores GROUP BY state",
 *   enrichment_metadata: {
 *     source_column: "state",
 *     enriched_fields: ["population"],
 *     total_enriched: 1,
 *     warnings: [],
 *     partial_failure: false
 *   },
 *   calculation_metadata: {
 *     calculated_columns: [
 *       {
 *         name: "residents_per_store",
 *         expression: "_enriched_population / store_count",
 *         format_type: "integer"
 *       }
 *     ],
 *     warnings: []
 *   }
 * };
 *
 * // Extracting numeric values for charts
 * import { extractNumericValue } from '../utils/chartHelpers';
 * const chartData = fullResult.rows.map(row => ({
 *   state: row.state,
 *   population: extractNumericValue(row._enriched_population), // Handles EnrichedValue
 *   perStore: extractNumericValue(row.residents_per_store)      // Handles CalculatedValue
 * }));
 * ```
 */
export interface QueryResult {
  /** Schema information for all columns (base, enriched, and calculated) */
  columns: ColumnInfo[];
  /** Data rows where values can be primitives, EnrichedValue, or CalculatedValue objects */
  rows: Record<string, unknown>[];
  /** Total number of rows returned (may be limited by LIMIT clause) */
  total_rows: number;
  /** Query execution time in milliseconds (from BigQuery) */
  query_time_ms: number;
  /** The actual SQL query that was executed */
  sql: string;
  /** Present if apply_enrichment() was called - contains enrichment details */
  enrichment_metadata?: EnrichmentMetadata;
  /** Present if add_calculated_column() was called - contains calculation details */
  calculation_metadata?: CalculationMetadata;
}

/**
 * A clarifying question from the AI agent with predefined options.
 *
 * @remarks
 * When the agent needs more information to answer a user query (e.g., ambiguous
 * column names, missing time ranges), it can return a clarifying question with
 * multiple choice options for the user to select.
 *
 * The frontend displays these as interactive question cards with clickable options.
 *
 * @example
 * ```typescript
 * const question: ClarifyingQuestion = {
 *   question: "Which table should I query?",
 *   options: [
 *     "orders - Contains order transactions",
 *     "order_history - Contains historical order data"
 *   ],
 *   context: "I found multiple tables that might contain this data."
 * };
 * ```
 */
export interface ClarifyingQuestion {
  /** The question text asking for clarification */
  question: string;
  /** List of possible answers (max 5 options) */
  options: string[];
  /** Optional additional context explaining why clarification is needed */
  context?: string;
}

/**
 * A proactive insight generated by the AI agent from query results.
 *
 * @remarks
 * After executing queries, the agent analyzes results to identify trends,
 * anomalies, comparisons, and suggestions that add value beyond the user's
 * immediate question.
 *
 * The frontend displays these as insight badges with appropriate styling
 * based on type and importance.
 *
 * **Insight Types**:
 * - `trend`: Directional changes over time (increasing, decreasing, stable)
 * - `anomaly`: Unusual values that deviate from the norm
 * - `comparison`: Relative performance vs averages or previous periods
 * - `suggestion`: Recommendations for further analysis
 *
 * @example
 * ```typescript
 * const insights: Insight[] = [
 *   {
 *     type: "trend",
 *     message: "Sales have increased 23% month-over-month",
 *     importance: "high"
 *   },
 *   {
 *     type: "anomaly",
 *     message: "Store #42 has unusually low revenue despite high foot traffic",
 *     importance: "medium"
 *   },
 *   {
 *     type: "suggestion",
 *     message: "You might want to compare this with last quarter's data",
 *     importance: "low"
 *   }
 * ];
 * ```
 */
export interface Insight {
  /** Category of insight */
  type: 'trend' | 'anomaly' | 'comparison' | 'suggestion';
  /** Human-readable insight message */
  message: string;
  /** Significance level of the insight */
  importance: 'low' | 'medium' | 'high';
}

/**
 * A message in the chat conversation between user and AI agent.
 *
 * @remarks
 * Represents a single turn in the conversation, which can include:
 * - Text content (always present)
 * - Query results from BigQuery (when agent executes a query)
 * - Clarifying questions (when agent needs more info)
 * - Proactive insights (when agent identifies patterns)
 *
 * Messages are displayed in the Chat panel with different formatting based
 * on role and content type.
 *
 * @example
 * ```typescript
 * // User message
 * const userMsg: ChatMessage = {
 *   id: "msg-user-123",
 *   role: "user",
 *   content: "Show me sales by state",
 *   timestamp: "2024-01-15T10:30:00Z",
 *   insights: []
 * };
 *
 * // Assistant message with query results
 * const assistantMsg: ChatMessage = {
 *   id: "msg-asst-124",
 *   role: "assistant",
 *   content: "Here are the sales by state for the last month:",
 *   timestamp: "2024-01-15T10:30:05Z",
 *   query_result: {
 *     columns: [...],
 *     rows: [...],
 *     total_rows: 50,
 *     query_time_ms: 234.56,
 *     sql: "SELECT state, SUM(sales) FROM orders GROUP BY state"
 *   },
 *   insights: [
 *     {
 *       type: "trend",
 *       message: "Sales in CA increased 15% from last month",
 *       importance: "high"
 *     }
 *   ]
 * };
 *
 * // Assistant message with clarifying question
 * const clarifyingMsg: ChatMessage = {
 *   id: "msg-asst-125",
 *   role: "assistant",
 *   content: "I found multiple tables. Which one should I query?",
 *   timestamp: "2024-01-15T10:31:00Z",
 *   clarifying_question: {
 *     question: "Which table should I query?",
 *     options: ["orders", "order_history"]
 *   },
 *   insights: []
 * };
 * ```
 */
export interface ChatMessage {
  /** Unique identifier for this message */
  id: string;
  /** Who sent this message */
  role: MessageRole;
  /** Text content of the message */
  content: string;
  /** ISO 8601 timestamp (UTC) */
  timestamp: string;
  /** Present if this message contains query results */
  query_result?: QueryResult;
  /** Present if the agent is asking a clarifying question */
  clarifying_question?: ClarifyingQuestion;
  /** List of proactive insights generated by the agent */
  insights: Insight[];
  /** True if this message is being streamed token-by-token (future feature) */
  is_streaming?: boolean;
}

/**
 * Metadata about a chat session.
 *
 * @remarks
 * Sessions group related messages together and maintain conversation context.
 * Session data is stored in-memory on the backend and lost on server restart.
 *
 * @example
 * ```typescript
 * const session: SessionInfo = {
 *   id: "550e8400-e29b-41d4-a716-446655440000",
 *   name: "Sales Analysis",
 *   created_at: "2024-01-15T10:00:00Z",
 *   updated_at: "2024-01-15T10:30:00Z",
 *   message_count: 12
 * };
 * ```
 */
export interface SessionInfo {
  /** Unique session identifier (UUID) */
  id: string;
  /** Human-readable name for the session */
  name?: string;
  /** ISO 8601 timestamp (UTC) when session was created */
  created_at: string;
  /** ISO 8601 timestamp (UTC) when session was last updated */
  updated_at: string;
  /** Total number of messages in this session */
  message_count: number;
}

/**
 * Event emitted during streaming response (future feature).
 *
 * @remarks
 * This interface is currently defined but not implemented. In the future,
 * the backend will stream responses token-by-token via WebSocket or SSE.
 *
 * **Event Types**:
 * - `start`: Stream started
 * - `token`: Text token received
 * - `query_start`: Query execution started
 * - `query_result`: Query completed with results
 * - `insight`: Insight generated
 * - `done`: Stream completed
 * - `error`: Error occurred
 *
 * @example
 * ```typescript
 * // Future streaming implementation
 * const events: StreamEvent[] = [
 *   { event_type: "start", data: {}, timestamp: "2024-01-15T10:30:00Z" },
 *   { event_type: "token", data: "Here", timestamp: "2024-01-15T10:30:00.100Z" },
 *   { event_type: "token", data: " are", timestamp: "2024-01-15T10:30:00.200Z" },
 *   { event_type: "query_start", data: { sql: "SELECT ..." }, timestamp: "2024-01-15T10:30:01Z" },
 *   { event_type: "query_result", data: { rows: [...] }, timestamp: "2024-01-15T10:30:05Z" },
 *   { event_type: "done", data: {}, timestamp: "2024-01-15T10:30:05.500Z" }
 * ];
 * ```
 */
export interface StreamEvent {
  /** Type of event being emitted */
  event_type: 'start' | 'token' | 'query_start' | 'query_result' | 'insight' | 'done' | 'error';
  /** Event payload (structure depends on event_type) */
  data: unknown;
  /** ISO 8601 timestamp (UTC) when event was emitted */
  timestamp: string;
}

/**
 * Response from the /api/chat endpoint.
 *
 * @remarks
 * Contains the AI agent's response message plus the full conversation history
 * to help the frontend maintain state.
 *
 * The session_id should be included in subsequent requests to continue the
 * same conversation.
 *
 * @example
 * ```typescript
 * // POST /api/chat
 * const response: ChatResponse = {
 *   session_id: "550e8400-e29b-41d4-a716-446655440000",
 *   message: {
 *     id: "msg-124",
 *     role: "assistant",
 *     content: "Here are the sales by state:",
 *     timestamp: "2024-01-15T10:30:05Z",
 *     query_result: { ... },
 *     insights: [ ... ]
 *   },
 *   conversation_history: [
 *     { id: "msg-123", role: "user", content: "Show me sales by state", ... },
 *     { id: "msg-124", role: "assistant", content: "Here are the sales...", ... }
 *   ]
 * };
 *
 * // Continue conversation
 * const followUpRequest = {
 *   message: "What about Texas specifically?",
 *   session_id: response.session_id  // Use same session ID
 * };
 * ```
 */
export interface ChatResponse {
  /** Session ID for this conversation (use in subsequent requests) */
  session_id: string;
  /** The AI agent's response message */
  message: ChatMessage;
  /** Full conversation history for this session (ordered chronologically) */
  conversation_history: ChatMessage[];
}
