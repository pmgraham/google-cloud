import { useState, useCallback } from 'react';
import type { ChatMessage } from '../types';
import { api } from '../services/api';

/**
 * Return type for the useChat hook.
 *
 * @remarks
 * Provides chat state management including messages, loading states, error handling,
 * and actions for sending messages and managing the conversation.
 */
interface UseChatReturn {
  /** Array of all messages in the current conversation (chronologically ordered) */
  messages: ChatMessage[];
  /** Current session ID (null before first message is sent) */
  sessionId: string | null;
  /** True while waiting for AI agent response */
  isLoading: boolean;
  /** Error message if last operation failed (null if no error) */
  error: string | null;
  /** Send a message to the AI agent */
  sendMessage: (message: string) => Promise<void>;
  /** Select an option from a clarifying question (sends as message) */
  selectOption: (option: string) => Promise<void>;
  /** Clear the current error state */
  clearError: () => void;
  /** Clear all messages and start a new session */
  clearChat: () => void;
}

/**
 * React hook for managing chat conversation state and API interactions.
 *
 * @remarks
 * This hook manages the entire chat conversation lifecycle:
 * - Message history (user and assistant messages)
 * - Session management (creates and maintains session ID)
 * - Loading states (while waiting for AI responses)
 * - Error handling (API failures, network errors)
 *
 * **State Flow**:
 * 1. User calls `sendMessage()` with text
 * 2. User message added to state immediately (optimistic update)
 * 3. `isLoading` set to true
 * 4. API request sent to backend
 * 5. Assistant response added to state when received
 * 6. `isLoading` set to false
 *
 * **Error Handling**:
 * If the API request fails, an error message is added to the conversation
 * as an assistant message, and the `error` state is set. Users can clear
 * errors with `clearError()`.
 *
 * **Session Management**:
 * - First message creates a new session (backend generates session ID)
 * - Session ID is stored and used for all subsequent messages
 * - `clearChat()` resets session and starts fresh
 *
 * @returns Chat state and actions for managing the conversation
 *
 * @example
 * ```tsx
 * function ChatInterface() {
 *   const {
 *     messages,
 *     isLoading,
 *     error,
 *     sendMessage,
 *     selectOption,
 *     clearChat
 *   } = useChat();
 *
 *   const handleSubmit = async (text: string) => {
 *     await sendMessage(text);
 *   };
 *
 *   const handleOptionClick = async (option: string) => {
 *     await selectOption(option);
 *   };
 *
 *   return (
 *     <div>
 *       {messages.map(msg => (
 *         <Message key={msg.id} message={msg} />
 *       ))}
 *       {isLoading && <LoadingSpinner />}
 *       {error && <ErrorAlert message={error} />}
 *       <ChatInput onSubmit={handleSubmit} disabled={isLoading} />
 *       <button onClick={clearChat}>New Chat</button>
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Handling clarifying questions
 * function ChatMessage({ message }: { message: ChatMessage }) {
 *   const { selectOption } = useChat();
 *
 *   if (message.clarifying_question) {
 *     return (
 *       <div>
 *         <p>{message.clarifying_question.question}</p>
 *         {message.clarifying_question.options.map(option => (
 *           <button
 *             key={option}
 *             onClick={() => selectOption(option)}
 *           >
 *             {option}
 *           </button>
 *         ))}
 *       </div>
 *     );
 *   }
 *
 *   return <p>{message.content}</p>;
 * }
 * ```
 */
export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Send a message to the AI agent and update conversation state.
   *
   * @param message - The user's message text to send
   *
   * @remarks
   * This function implements an optimistic UI update pattern:
   * 1. User message is added immediately (before API response)
   * 2. Loading state is set
   * 3. API request is sent with current session ID
   * 4. Session ID is captured from first response
   * 5. Assistant response is added when received
   * 6. Errors are caught and displayed as assistant messages
   *
   * The function will not send empty or whitespace-only messages.
   *
   * @example
   * ```tsx
   * const { sendMessage, isLoading } = useChat();
   *
   * const handleSubmit = async (text: string) => {
   *   await sendMessage(text);
   *   // Message is now in the conversation
   * };
   * ```
   */
  const sendMessage = useCallback(async (message: string) => {
    if (!message.trim()) return;

    setIsLoading(true);
    setError(null);

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
      insights: [],
    };

    setMessages((prev) => [...prev, userMessage]);

    try {
      const response = await api.sendMessage(message, sessionId || undefined);

      // Update session ID if new
      if (!sessionId) {
        setSessionId(response.session_id);
      }

      // Add assistant message
      setMessages((prev) => {
        // Remove any streaming placeholder and add the final message
        const withoutStreaming = prev.filter((m) => !m.is_streaming);
        return [...withoutStreaming, response.message];
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMessage);

      // Add error message as assistant response
      const errorResponse: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `I encountered an error: ${errorMessage}. Please try again.`,
        timestamp: new Date().toISOString(),
        insights: [],
      };

      setMessages((prev) => [...prev, errorResponse]);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  /**
   * Select an option from a clarifying question.
   *
   * @param option - The option text selected by the user
   *
   * @remarks
   * When the AI agent asks a clarifying question (e.g., "Which table?"),
   * this function sends the user's selected option as a regular message.
   * This is a convenience wrapper around `sendMessage()`.
   *
   * @example
   * ```tsx
   * function ClarifyingOptions({ question }: { question: ClarifyingQuestion }) {
   *   const { selectOption } = useChat();
   *
   *   return (
   *     <div>
   *       <p>{question.question}</p>
   *       {question.options.map(opt => (
   *         <button key={opt} onClick={() => selectOption(opt)}>
   *           {opt}
   *         </button>
   *       ))}
   *     </div>
   *   );
   * }
   * ```
   */
  const selectOption = useCallback(async (option: string) => {
    // When user selects a clarifying option, send it as a message
    await sendMessage(option);
  }, [sendMessage]);

  /**
   * Clear the current error state.
   *
   * @remarks
   * Resets the `error` state to null without affecting messages or session.
   * Used to dismiss error notifications after the user has acknowledged them.
   *
   * @example
   * ```tsx
   * function ErrorAlert() {
   *   const { error, clearError } = useChat();
   *
   *   if (!error) return null;
   *
   *   return (
   *     <div className="error-banner">
   *       <p>{error}</p>
   *       <button onClick={clearError}>Dismiss</button>
   *     </div>
   *   );
   * }
   * ```
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Clear all messages and start a new chat session.
   *
   * @remarks
   * Resets all chat state to initial values:
   * - Clears message history
   * - Resets session ID (next message will create new session)
   * - Clears any errors
   *
   * This effectively starts a completely fresh conversation with the AI agent.
   *
   * @example
   * ```tsx
   * function ChatHeader() {
   *   const { clearChat, messages } = useChat();
   *
   *   return (
   *     <div className="chat-header">
   *       <h1>Data Insights Chat</h1>
   *       {messages.length > 0 && (
   *         <button onClick={clearChat}>
   *           New Chat
   *         </button>
   *       )}
   *     </div>
   *   );
   * }
   * ```
   */
  const clearChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setError(null);
  }, []);

  return {
    messages,
    sessionId,
    isLoading,
    error,
    sendMessage,
    selectOption,
    clearError,
    clearChat,
  };
}
