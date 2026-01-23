import { useState, useCallback, useRef, useEffect } from 'react';
import type { StreamEvent, QueryResult } from '../types';

/**
 * Options for configuring WebSocket behavior and event handlers.
 *
 * @remarks
 * **IMPORTANT**: This hook is currently defined but WebSocket streaming is NOT YET IMPLEMENTED
 * on the backend. The backend returns complete responses via HTTP, not streaming via WebSocket.
 *
 * This interface documents the intended future streaming API.
 */
interface UseWebSocketOptions {
  /** Session ID for this chat conversation */
  sessionId: string;
  /** Callback invoked for each token received during streaming */
  onToken?: (text: string) => void;
  /** Callback invoked when query results are received */
  onQueryResult?: (result: QueryResult) => void;
  /** Callback invoked when streaming completes */
  onComplete?: (message: string, queryResult?: QueryResult) => void;
  /** Callback invoked on connection or streaming errors */
  onError?: (error: string) => void;
}

/**
 * Return type for the useWebSocket hook.
 *
 * @remarks
 * Provides WebSocket connection state and methods for managing the connection.
 *
 * **FUTURE FEATURE**: WebSocket streaming is not yet implemented. This hook is
 * prepared for future backend streaming support.
 */
interface UseWebSocketReturn {
  /** True if WebSocket connection is established */
  isConnected: boolean;
  /** True if currently receiving a streamed response */
  isStreaming: boolean;
  /** Establish WebSocket connection to server */
  connect: () => void;
  /** Close WebSocket connection */
  disconnect: () => void;
  /** Send a message through the WebSocket connection */
  sendMessage: (message: string) => void;
}

/**
 * React hook for managing WebSocket connections for streaming chat responses.
 *
 * @param options - Configuration options and event handlers
 * @returns WebSocket connection state and control methods
 *
 * @remarks
 * **⚠️ FUTURE FEATURE**: This hook is currently defined but NOT FUNCTIONAL because
 * WebSocket streaming is not yet implemented on the backend. The current implementation
 * uses standard HTTP requests via the `/api/chat` endpoint.
 *
 * **Intended Behavior** (when implemented):
 * - Establishes WebSocket connection to `/ws/{sessionId}`
 * - Receives streamed tokens as the AI generates responses
 * - Processes stream events: start, token, query_result, done, error
 * - Accumulates tokens into complete messages
 * - Handles query results when received during streaming
 * - Automatically cleans up connection on unmount
 *
 * **Stream Event Flow**:
 * 1. `start`: Stream begins, reset accumulators
 * 2. `token`: Text token received, call `onToken()` callback
 * 3. `query_result`: Query completed, call `onQueryResult()` callback
 * 4. `done`: Stream complete, call `onComplete()` with full message
 * 5. `error`: Error occurred, call `onError()` callback
 *
 * **Connection Management**:
 * - Auto-connects when `connect()` is called
 * - Auto-disconnects on unmount
 * - Handles reconnection on connection loss
 * - Uses secure WebSocket (wss://) when page is served over HTTPS
 *
 * @example
 * ```tsx
 * // Future usage when backend supports streaming
 * function StreamingChat({ sessionId }: { sessionId: string }) {
 *   const [streamedText, setStreamedText] = useState('');
 *   const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
 *
 *   const {
 *     isConnected,
 *     isStreaming,
 *     connect,
 *     sendMessage
 *   } = useWebSocket({
 *     sessionId,
 *     onToken: (token) => {
 *       // Append each token as it arrives
 *       setStreamedText(prev => prev + token);
 *     },
 *     onQueryResult: (result) => {
 *       // Display query results immediately
 *       setQueryResult(result);
 *     },
 *     onComplete: (message, result) => {
 *       console.log('Stream complete:', message);
 *     },
 *     onError: (error) => {
 *       console.error('Stream error:', error);
 *     }
 *   });
 *
 *   useEffect(() => {
 *     connect();  // Connect on mount
 *   }, [connect]);
 *
 *   const handleSubmit = (text: string) => {
 *     setStreamedText('');  // Reset
 *     sendMessage(text);
 *   };
 *
 *   return (
 *     <div>
 *       <div className="status">
 *         {isConnected ? 'Connected' : 'Disconnected'}
 *         {isStreaming && ' - Streaming...'}
 *       </div>
 *       <div className="response">{streamedText}</div>
 *       {queryResult && <DataTable result={queryResult} />}
 *       <ChatInput onSubmit={handleSubmit} disabled={!isConnected || isStreaming} />
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Current workaround (use useChat instead)
 * import { useChat } from './useChat';
 *
 * function CurrentChat() {
 *   // Use useChat which uses HTTP endpoint
 *   const { messages, sendMessage, isLoading } = useChat();
 *
 *   return (
 *     <div>
 *       {messages.map(msg => <Message key={msg.id} message={msg} />)}
 *       <ChatInput onSubmit={sendMessage} disabled={isLoading} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useWebSocket({
  sessionId,
  onToken,
  onQueryResult,
  onComplete,
  onError,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const accumulatedTextRef = useRef('');
  const queryResultRef = useRef<QueryResult | undefined>(undefined);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsStreaming(false);
    };

    ws.onerror = () => {
      onError?.('WebSocket connection error');
      setIsConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const streamEvent: StreamEvent = JSON.parse(event.data);

        switch (streamEvent.event_type) {
          case 'start':
            setIsStreaming(true);
            accumulatedTextRef.current = '';
            queryResultRef.current = undefined;
            break;

          case 'token':
            const tokenData = streamEvent.data as { text: string };
            accumulatedTextRef.current += tokenData.text;
            onToken?.(tokenData.text);
            break;

          case 'query_result':
            queryResultRef.current = streamEvent.data as QueryResult;
            onQueryResult?.(queryResultRef.current);
            break;

          case 'done':
            setIsStreaming(false);
            const doneData = streamEvent.data as { message: string; query_result?: QueryResult };
            onComplete?.(
              doneData.message || accumulatedTextRef.current,
              doneData.query_result || queryResultRef.current
            );
            break;

          case 'error':
            setIsStreaming(false);
            const errorData = streamEvent.data as { error: string };
            onError?.(errorData.error);
            break;
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    wsRef.current = ws;
  }, [sessionId, onToken, onQueryResult, onComplete, onError]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message }));
    } else {
      onError?.('WebSocket is not connected');
    }
  }, [onError]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isStreaming,
    connect,
    disconnect,
    sendMessage,
  };
}
