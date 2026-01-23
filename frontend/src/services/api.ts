import type { ChatResponse, SessionInfo } from '../types';

/**
 * Base path for all API endpoints.
 *
 * @remarks
 * All API methods prepend this base path to endpoint URLs. This allows the
 * API to be served from a different path if needed (e.g., behind a reverse proxy).
 */
const API_BASE = '/api';

/**
 * Custom error class for API request failures.
 *
 * @remarks
 * Extends the standard Error class to include HTTP status code and additional
 * error details from the backend. This provides more context for error handling
 * and logging.
 *
 * @example
 * ```typescript
 * try {
 *   await api.sendMessage("test");
 * } catch (error) {
 *   if (error instanceof ApiError) {
 *     console.error('API Error:', error.message);
 *     console.error('Status:', error.status);
 *     console.error('Detail:', error.detail);
 *
 *     if (error.status === 404) {
 *       showNotFoundMessage();
 *     } else if (error.status >= 500) {
 *       showServerErrorMessage();
 *     }
 *   }
 * }
 * ```
 */
class ApiError extends Error {
  /**
   * Create an ApiError instance.
   *
   * @param message - Error message (from backend error.error field or default)
   * @param status - HTTP status code (e.g., 404, 500)
   * @param detail - Optional additional error details from backend
   */
  constructor(
    message: string,
    public status: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Parse and validate HTTP response, throwing ApiError on failure.
 *
 * @typeParam T - Expected response body type
 * @param response - Fetch API response object
 * @returns Parsed JSON response body
 * @throws {ApiError} If response status is not OK (2xx)
 *
 * @remarks
 * This helper function:
 * 1. Checks if HTTP status is successful (2xx)
 * 2. Parses JSON response body
 * 3. Throws ApiError with status code and details if request failed
 * 4. Handles cases where error response is not valid JSON
 *
 * Used internally by all API methods to standardize error handling.
 *
 * @example
 * ```typescript
 * // Internal usage in API methods
 * async function sendMessage(message: string): Promise<ChatResponse> {
 *   const response = await fetch('/api/chat', {
 *     method: 'POST',
 *     body: JSON.stringify({ message })
 *   });
 *   return handleResponse<ChatResponse>(response);  // Throws ApiError if failed
 * }
 * ```
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(
      error.error || 'Request failed',
      response.status,
      error.detail
    );
  }
  return response.json();
}

/**
 * Centralized API client for all backend communication.
 *
 * @remarks
 * This object provides a type-safe interface to all backend REST API endpoints.
 * All methods return promises and throw `ApiError` on failure.
 *
 * **Endpoints**:
 * - **Health**: System status and version info
 * - **Sessions**: Create, list, get, delete chat sessions
 * - **Chat**: Send messages to AI agent
 * - **Schema**: Get BigQuery table metadata
 *
 * **Error Handling**:
 * All methods can throw `ApiError` with status code and detail. Use try/catch
 * blocks or React Query error boundaries to handle failures.
 *
 * @example
 * ```typescript
 * import { api, ApiError } from './services/api';
 *
 * try {
 *   const response = await api.sendMessage("Show me sales");
 *   console.log(response.message);
 * } catch (error) {
 *   if (error instanceof ApiError) {
 *     alert(`Error ${error.status}: ${error.message}`);
 *   }
 * }
 * ```
 */
export const api = {
  /**
   * Check backend health and get version information.
   *
   * @returns Object containing status and version
   * @throws {ApiError} If backend is unreachable or unhealthy
   *
   * @remarks
   * Used to verify backend connectivity and version compatibility.
   * Useful for startup health checks and monitoring.
   *
   * @example
   * ```typescript
   * const health = await api.healthCheck();
   * console.log(health.status);   // "healthy"
   * console.log(health.version);  // "1.0.0"
   * ```
   */
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${API_BASE}/health`);
    return handleResponse(response);
  },

  /**
   * Create a new chat session.
   *
   * @param name - Optional human-readable name for the session
   * @returns Session metadata including generated session ID
   * @throws {ApiError} If session creation fails
   *
   * @remarks
   * Creates a new session on the backend for organizing chat conversations.
   * Sessions maintain conversation context across multiple messages.
   *
   * **Note**: Sessions are stored in-memory on the backend and are lost on server restart.
   *
   * @example
   * ```typescript
   * const session = await api.createSession("Sales Analysis");
   * console.log(session.id);    // "550e8400-e29b-41d4-a716-446655440000"
   * console.log(session.name);  // "Sales Analysis"
   * ```
   */
  async createSession(name?: string): Promise<SessionInfo> {
    const response = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  /**
   * List all active chat sessions.
   *
   * @returns Object containing array of session metadata
   * @throws {ApiError} If request fails
   *
   * @remarks
   * Returns metadata for all sessions currently in backend memory.
   * Useful for displaying a session list or sidebar.
   *
   * @example
   * ```typescript
   * const { sessions } = await api.listSessions();
   * sessions.forEach(s => {
   *   console.log(`${s.name}: ${s.message_count} messages`);
   * });
   * ```
   */
  async listSessions(): Promise<{ sessions: SessionInfo[] }> {
    const response = await fetch(`${API_BASE}/sessions`);
    return handleResponse(response);
  },

  /**
   * Get metadata for a specific session.
   *
   * @param sessionId - The session ID to retrieve
   * @returns Session metadata including message count
   * @throws {ApiError} If session not found (404) or request fails
   *
   * @example
   * ```typescript
   * const session = await api.getSession("550e8400-...");
   * console.log(`${session.name} has ${session.message_count} messages`);
   * ```
   */
  async getSession(sessionId: string): Promise<SessionInfo> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`);
    return handleResponse(response);
  },

  /**
   * Delete a chat session and all its messages.
   *
   * @param sessionId - The session ID to delete
   * @throws {ApiError} If session not found (404) or deletion fails
   *
   * @remarks
   * Permanently deletes the session and all conversation history.
   * This action cannot be undone.
   *
   * @example
   * ```typescript
   * await api.deleteSession("550e8400-...");
   * console.log("Session deleted");
   * ```
   */
  async deleteSession(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
      method: 'DELETE',
    });
    await handleResponse(response);
  },

  /**
   * Send a message to the AI agent and receive a response.
   *
   * @param message - The user's message text
   * @param sessionId - Optional session ID to continue existing conversation
   * @returns Chat response including AI message, query results, and conversation history
   * @throws {ApiError} If request fails or agent encounters an error
   *
   * @remarks
   * **MAIN CHAT ENDPOINT** - This is the primary method for interacting with the AI agent.
   *
   * **Workflow**:
   * 1. If no sessionId provided, backend creates a new session
   * 2. Message is sent to AI agent (gemini-3-flash-preview)
   * 3. Agent processes message (may execute BigQuery queries, enrichment, calculations)
   * 4. Response includes:
   *    - Assistant message with text response
   *    - Query results (if agent executed a query)
   *    - Insights (trends, anomalies, suggestions)
   *    - Clarifying questions (if agent needs more info)
   *    - Full conversation history
   *
   * **Response Time**:
   * - Simple questions: ~2-5 seconds
   * - With BigQuery query: ~3-10 seconds
   * - With enrichment: ~10-30 seconds (depends on Google Search API)
   *
   * @example
   * ```typescript
   * // First message (creates new session)
   * const response1 = await api.sendMessage("Show me sales by state");
   * console.log(response1.session_id);  // "550e8400-..."
   * console.log(response1.message.query_result.total_rows);  // 50
   *
   * // Follow-up message (continues conversation)
   * const response2 = await api.sendMessage(
   *   "What about Texas?",
   *   response1.session_id
   * );
   * ```
   *
   * @example
   * ```typescript
   * // Handle query results
   * const response = await api.sendMessage("Show top 10 products");
   * if (response.message.query_result) {
   *   const { columns, rows, sql } = response.message.query_result;
   *   console.log(`Query: ${sql}`);
   *   console.log(`Returned ${rows.length} rows`);
   * }
   * ```
   *
   * @example
   * ```typescript
   * // Handle clarifying questions
   * const response = await api.sendMessage("Show me the data");
   * if (response.message.clarifying_question) {
   *   const { question, options } = response.message.clarifying_question;
   *   console.log(question);  // "Which table should I query?"
   *   options.forEach(opt => console.log(`- ${opt}`));
   * }
   * ```
   */
  async sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    return handleResponse(response);
  },

  /**
   * Get list of all available BigQuery tables in the dataset.
   *
   * @returns Object containing dataset name and array of table metadata
   * @throws {ApiError} If request fails or BigQuery is unavailable
   *
   * @remarks
   * Returns metadata for all tables accessible in the configured BigQuery dataset.
   * Each table includes column information, row counts, and descriptions.
   *
   * Useful for:
   * - Displaying available data sources to users
   * - Building table selection UI
   * - Understanding schema before querying
   *
   * @example
   * ```typescript
   * const { dataset, tables } = await api.getTables();
   * console.log(`Dataset: ${dataset}`);
   * tables.forEach(table => {
   *   console.log(`${table.name}: ${table.num_rows} rows, ${table.columns.length} columns`);
   * });
   * ```
   *
   * @example
   * ```typescript
   * // Build table selector
   * function TableSelector() {
   *   const [tables, setTables] = useState([]);
   *
   *   useEffect(() => {
   *     api.getTables().then(data => setTables(data.tables));
   *   }, []);
   *
   *   return (
   *     <select>
   *       {tables.map(t => (
   *         <option key={t.name} value={t.name}>
   *           {t.name} ({t.num_rows.toLocaleString()} rows)
   *         </option>
   *       ))}
   *     </select>
   *   );
   * }
   * ```
   */
  async getTables(): Promise<{
    status: string;
    dataset: string;
    tables: Array<{
      name: string;
      full_name: string;
      description: string;
      num_rows: number;
      columns: Array<{ name: string; type: string; description: string }>;
    }>;
  }> {
    const response = await fetch(`${API_BASE}/schema/tables`);
    return handleResponse(response);
  },

  /**
   * Get detailed schema information for a specific BigQuery table.
   *
   * @param tableName - Name of the table to get schema for
   * @returns Object containing table columns and sample rows
   * @throws {ApiError} If table not found (404) or request fails
   *
   * @remarks
   * Returns detailed column metadata and sample rows for a specific table.
   * Sample rows are limited to first 5 rows for preview purposes.
   *
   * Useful for:
   * - Understanding table structure before querying
   * - Displaying table previews
   * - Validating column names and types
   *
   * @example
   * ```typescript
   * const schema = await api.getTableSchema("orders");
   * console.log(`Table: ${schema.table_name}`);
   * schema.columns.forEach(col => {
   *   console.log(`- ${col.name}: ${col.type}`);
   * });
   * console.log(`Sample data (${schema.sample_rows.length} rows):`);
   * console.log(schema.sample_rows);
   * ```
   *
   * @example
   * ```typescript
   * // Table preview component
   * function TablePreview({ tableName }: { tableName: string }) {
   *   const [schema, setSchema] = useState(null);
   *
   *   useEffect(() => {
   *     api.getTableSchema(tableName).then(setSchema);
   *   }, [tableName]);
   *
   *   if (!schema) return <div>Loading...</div>;
   *
   *   return (
   *     <div>
   *       <h3>{schema.table_name}</h3>
   *       <table>
   *         <thead>
   *           <tr>
   *             {schema.columns.map(col => (
   *               <th key={col.name}>{col.name} ({col.type})</th>
   *             ))}
   *           </tr>
   *         </thead>
   *         <tbody>
   *           {schema.sample_rows.map((row, i) => (
   *             <tr key={i}>
   *               {schema.columns.map(col => (
   *                 <td key={col.name}>{String(row[col.name] ?? '')}</td>
   *               ))}
   *             </tr>
   *           ))}
   *         </tbody>
   *       </table>
   *     </div>
   *   );
   * }
   * ```
   */
  async getTableSchema(tableName: string): Promise<{
    status: string;
    table_name: string;
    columns: Array<{ name: string; type: string; description: string }>;
    sample_rows: Array<Record<string, unknown>>;
  }> {
    const response = await fetch(`${API_BASE}/schema/tables/${encodeURIComponent(tableName)}`);
    return handleResponse(response);
  },
};

export { ApiError };
