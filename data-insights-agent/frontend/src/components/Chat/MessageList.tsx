import { useEffect, useRef } from 'react';
import { User, Bot, Lightbulb, TrendingUp, AlertCircle, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage, Insight } from '../../types';
import { ClarificationPrompt } from './ClarificationPrompt';

/**
 * Props for the MessageList component.
 *
 * @remarks
 * Defines the data and event handlers for rendering the message history.
 */
interface MessageListProps {
  /** Array of chat messages to display (user messages and agent responses) */
  messages: ChatMessage[];
  /** Whether the agent is currently processing (shows loading animation) */
  isLoading: boolean;
  /** Callback invoked when user selects a clarifying question option or starter suggestion */
  onSelectOption: (option: string) => void;
  /** Optional callback invoked when user clicks "View results" button on a message with query_result */
  onViewResults?: (message: ChatMessage) => void;
}

/**
 * Insight badge component displaying AI-generated insights.
 *
 * @param props - Component props with single insight object
 * @returns Styled badge with icon and insight message
 *
 * @remarks
 * Displays an Insight object (trend, anomaly, comparison, suggestion) with
 * appropriate icon and color scheme.
 *
 * **Insight Types**:
 * - `trend`: Blue (TrendingUp icon) - Data trends over time
 * - `anomaly`: Amber (AlertCircle icon) - Unusual patterns or outliers
 * - `comparison`: Purple (Sparkles icon) - Comparative analysis
 * - `suggestion`: Green (Lightbulb icon) - Recommendations or next steps
 */
function InsightBadge({ insight }: { insight: Insight }) {
  const icons = {
    trend: TrendingUp,
    anomaly: AlertCircle,
    comparison: Sparkles,
    suggestion: Lightbulb,
  };

  const colors = {
    trend: 'bg-blue-50 text-blue-700 border-blue-200',
    anomaly: 'bg-amber-50 text-amber-700 border-amber-200',
    comparison: 'bg-purple-50 text-purple-700 border-purple-200',
    suggestion: 'bg-green-50 text-green-700 border-green-200',
  };

  const Icon = icons[insight.type] || Lightbulb;
  const colorClass = colors[insight.type] || colors.suggestion;

  return (
    <div className={`flex items-start gap-2 px-3 py-2 rounded-lg border ${colorClass}`}>
      <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
      <p className="text-sm">{insight.message}</p>
    </div>
  );
}

/**
 * Message list component that displays chat history with auto-scroll.
 *
 * @param props - Component props
 * @returns Scrollable message list with empty state, messages, insights, and loading indicator
 *
 * @remarks
 * **Primary message display component** that renders the conversation history
 * between user and AI agent.
 *
 * **Features**:
 * - **Auto-scroll**: Scrolls to bottom when new messages arrive
 * - **Empty state**: Shows welcome message and starter suggestions when no messages exist
 * - **Message rendering**:
 *   - User messages: Right-aligned, blue background, plain text
 *   - Agent messages: Left-aligned, white background, markdown rendering
 * - **Rich content**:
 *   - Clarifying questions: Inline amber prompts with selectable options
 *   - Query results: "View results" button to open ResultsPanel
 *   - Insights: Colored badges for trends, anomalies, comparisons, suggestions
 * - **Loading state**: Animated dots with "Thinking..." label
 *
 * **Auto-Scroll Behavior**:
 * Uses `useEffect` hook with `bottomRef` to scroll to bottom whenever:
 * - New message added to `messages` array
 * - `isLoading` state changes
 * Uses smooth scrolling for better UX.
 *
 * **Message Structure**:
 * Each ChatMessage can contain:
 * - `content`: Main text (markdown for agent, plain for user)
 * - `clarifying_question`: Optional ClarifyingQuestion object
 * - `query_result`: Optional QueryResult object (triggers "View results" button)
 * - `insights`: Optional array of Insight objects
 *
 * **Empty State**:
 * Shown when `messages.length === 0` and not loading:
 * - Bot icon with welcome message
 * - Example questions as clickable buttons
 * - Calls `onSelectOption` when suggestion clicked
 *
 * **Avatar Icons**:
 * - User: Gray circle with User icon
 * - Agent: Primary-colored circle with Bot icon
 *
 * @example
 * ```tsx
 * import { MessageList } from './MessageList';
 *
 * function ChatPanel() {
 *   const { messages, isLoading } = useChat();
 *
 *   return (
 *     <div className="flex flex-col h-screen">
 *       <MessageList
 *         messages={messages}
 *         isLoading={isLoading}
 *         onSelectOption={handleSend}
 *         onViewResults={openResultsPanel}
 *       />
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Message with insights and clarifying question
 * const messageWithExtras: ChatMessage = {
 *   id: '1',
 *   role: 'assistant',
 *   content: 'I found some interesting patterns...',
 *   insights: [
 *     { type: 'trend', message: 'Sales increased 23% in Q4' },
 *     { type: 'anomaly', message: 'Spike detected on Dec 15th' }
 *   ],
 *   clarifying_question: {
 *     question: 'Which region should I focus on?',
 *     options: ['North America', 'Europe', 'Asia']
 *   }
 * };
 *
 * <MessageList messages={[messageWithExtras]} isLoading={false} onSelectOption={handleSelect} />
 * // Renders message with 2 insight badges and clarification prompt
 * ```
 */
export function MessageList({
  messages,
  isLoading,
  onSelectOption,
  onViewResults,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mb-4">
          <Bot className="w-8 h-8 text-primary-600" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Ask me anything about your data
        </h3>
        <p className="text-gray-500 max-w-md">
          I can help you explore your BigQuery data using natural language.
          Try asking questions like "What were our top 10 products last month?"
          or "Show me revenue trends by region."
        </p>
        <div className="mt-6 flex flex-wrap gap-2 justify-center">
          {[
            'What tables are available?',
            'Show me recent data trends',
            'What are the top performing items?',
          ].map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSelectOption(suggestion)}
              className="px-4 py-2 text-sm bg-white border border-gray-200 rounded-full hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          {message.role === 'assistant' && (
            <div className="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
              <Bot className="w-4 h-4 text-primary-600" />
            </div>
          )}

          <div
            className={`max-w-[80%] ${
              message.role === 'user'
                ? 'bg-primary-600 text-white rounded-2xl rounded-tr-sm px-4 py-3'
                : 'bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm'
            }`}
          >
            {message.role === 'user' ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className="prose prose-sm max-w-none prose-headings:mt-3 prose-headings:mb-2 prose-p:my-1 prose-ul:my-1 prose-li:my-0 prose-table:text-sm">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            )}

            {/* Clarifying question */}
            {message.clarifying_question && (
              <div className="mt-3">
                <ClarificationPrompt
                  question={message.clarifying_question}
                  onSelect={onSelectOption}
                />
              </div>
            )}

            {/* Query results indicator */}
            {message.query_result && (
              <button
                onClick={() => onViewResults?.(message)}
                className="mt-3 flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 rounded-lg text-sm text-gray-700 transition-colors"
              >
                <TrendingUp className="w-4 h-4" />
                View results ({message.query_result.total_rows} rows)
              </button>
            )}

            {/* Insights */}
            {message.insights && message.insights.length > 0 && (
              <div className="mt-3 space-y-2">
                {message.insights.map((insight, idx) => (
                  <InsightBadge key={idx} insight={insight} />
                ))}
              </div>
            )}
          </div>

          {message.role === 'user' && (
            <div className="flex-shrink-0 w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-gray-600" />
            </div>
          )}
        </div>
      ))}

      {/* Loading indicator */}
      {isLoading && (
        <div className="flex gap-3">
          <div className="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
            <Bot className="w-4 h-4 text-primary-600" />
          </div>
          <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span className="text-sm text-gray-500">Thinking...</span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
