export type MessageRole = 'user' | 'assistant' | 'system';

export type ChartType = 'table' | 'bar' | 'line' | 'pie' | 'area';

export interface ColumnInfo {
  name: string;
  type: string;
  is_enriched?: boolean;
}

export interface EnrichedValue {
  value: unknown;
  source: string | null;
  confidence: 'high' | 'medium' | 'low' | null;
  freshness: 'static' | 'current' | 'dated' | 'stale' | null;
  warning: string | null;
}

export interface EnrichmentMetadata {
  source_column: string;
  enriched_fields: string[];
  total_enriched: number;
  warnings: string[];
  partial_failure: boolean;
}

export interface QueryResult {
  columns: ColumnInfo[];
  rows: Record<string, unknown>[];
  total_rows: number;
  query_time_ms: number;
  sql: string;
  enrichment_metadata?: EnrichmentMetadata;
}

export interface ClarifyingQuestion {
  question: string;
  options: string[];
  context?: string;
}

export interface Insight {
  type: 'trend' | 'anomaly' | 'comparison' | 'suggestion';
  message: string;
  importance: 'low' | 'medium' | 'high';
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  query_result?: QueryResult;
  clarifying_question?: ClarifyingQuestion;
  insights: Insight[];
  is_streaming?: boolean;
}

export interface SessionInfo {
  id: string;
  name?: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface StreamEvent {
  event_type: 'start' | 'token' | 'query_start' | 'query_result' | 'insight' | 'done' | 'error';
  data: unknown;
  timestamp: string;
}

export interface ChatResponse {
  session_id: string;
  message: ChatMessage;
  conversation_history: ChatMessage[];
}
