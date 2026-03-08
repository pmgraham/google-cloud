import type { ChatMessage } from '../../types';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';

/**
 * Props for the ChatPanel component.
 *
 * @remarks
 * Defines the data and event handlers for the main chat interface.
 */
interface ChatPanelProps {
  /** Array of chat messages to display (user messages and agent responses) */
  messages: ChatMessage[];
  /** Whether the agent is currently processing a query */
  isLoading: boolean;
  /** Callback invoked when user submits a new message */
  onSendMessage: (message: string) => void;
  /** Callback invoked when user selects a clarifying question option or suggestion */
  onSelectOption: (option: string) => void;
  /** Optional callback invoked when user clicks "View results" button on a message with query_result */
  onViewResults?: (message: ChatMessage) => void;
}

/**
 * Main chat panel container component.
 *
 * @param props - Component props
 * @returns Chat interface with message list and input field
 *
 * @remarks
 * **Primary chat interface component** that orchestrates the conversation between
 * user and AI agent.
 *
 * **Structure**:
 * - Top section: MessageList (scrollable message history)
 * - Bottom section: MessageInput (fixed input field)
 * - Layout: Flexbox column filling full height
 *
 * **State Management**:
 * This component is stateless - all state is managed by parent (App.tsx via useChat hook):
 * - `messages`: Chat history array
 * - `isLoading`: Agent processing state
 * - Event handlers: Passed down from parent to child components
 *
 * **Event Flow**:
 * 1. User types message in MessageInput → `onSendMessage()` called
 * 2. Parent (App) sends to backend API via useChat hook
 * 3. Agent response received → new message added to `messages` array
 * 4. MessageList auto-scrolls to show new message
 *
 * **Child Components**:
 * - `MessageList`: Displays message history, insights, clarifying questions, and results buttons
 * - `MessageInput`: Auto-resizing textarea with submit button and keyboard shortcuts
 *
 * @example
 * ```tsx
 * import { ChatPanel } from './components/Chat/ChatPanel';
 *
 * function App() {
 *   const { messages, isLoading, sendMessage } = useChat();
 *   const [selectedMessage, setSelectedMessage] = useState<ChatMessage | null>(null);
 *
 *   return (
 *     <div className="flex h-screen">
 *       <div className="flex-1">
 *         <ChatPanel
 *           messages={messages}
 *           isLoading={isLoading}
 *           onSendMessage={sendMessage}
 *           onSelectOption={sendMessage}  // Treat option selection as new message
 *           onViewResults={setSelectedMessage}
 *         />
 *       </div>
 *       {selectedMessage && (
 *         <ResultsPanel message={selectedMessage} onClose={() => setSelectedMessage(null)} />
 *       )}
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Minimal usage without results panel
 * <ChatPanel
 *   messages={messages}
 *   isLoading={isLoading}
 *   onSendMessage={handleSend}
 *   onSelectOption={handleSend}
 * />
 * ```
 */
export function ChatPanel({
  messages,
  isLoading,
  onSendMessage,
  onSelectOption,
  onViewResults,
}: ChatPanelProps) {
  return (
    <div className="flex flex-col h-full bg-gray-50">
      <MessageList
        messages={messages}
        isLoading={isLoading}
        onSelectOption={onSelectOption}
        onViewResults={onViewResults}
      />
      <MessageInput onSend={onSendMessage} isLoading={isLoading} />
    </div>
  );
}
