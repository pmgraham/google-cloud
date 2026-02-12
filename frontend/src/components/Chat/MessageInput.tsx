import { useState, useRef, KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

/**
 * Props for the MessageInput component.
 *
 * @remarks
 * Configures the behavior and appearance of the message input field.
 */
interface MessageInputProps {
  /** Callback invoked when user submits a message (Enter key or Send button) */
  onSend: (message: string) => void;
  /** Whether submission is disabled (agent is processing) */
  isLoading: boolean;
  /** Optional placeholder text for the textarea (default: "Ask a question about your data...") */
  placeholder?: string;
}

/**
 * Auto-resizing message input field with submit button.
 *
 * @param props - Component props
 * @returns Message input UI with textarea and send button
 *
 * @remarks
 * **Interactive input component** for chat messages with auto-resize and keyboard shortcuts.
 *
 * **Features**:
 * - **Auto-resize**: Textarea expands as user types (max height: 200px)
 * - **Keyboard shortcuts**:
 *   - `Enter`: Submit message
 *   - `Shift+Enter`: New line
 * - **Disabled state**: Input and button disabled while `isLoading` is true
 * - **Auto-reset**: Clears input and resets height after submission
 *
 * **State Management**:
 * - `input`: Current textarea value (controlled component)
 * - `textareaRef`: Reference to textarea DOM element for height manipulation
 *
 * **Event Handlers**:
 * - `handleSubmit()`: Trims whitespace, validates non-empty, calls `onSend()`, clears input
 * - `handleKeyDown()`: Detects Enter key (without Shift) and submits
 * - `handleInput()`: Calculates scroll height and adjusts textarea height dynamically
 *
 * **Auto-Resize Logic**:
 * 1. User types → `handleInput()` fired
 * 2. Reset height to `auto` (collapses to content)
 * 3. Read `scrollHeight` (actual content height)
 * 4. Set height to `min(scrollHeight, 200px)`
 * 5. Result: Textarea grows with content, capped at 200px
 *
 * **UI Details**:
 * - Minimum height: 48px (single line)
 * - Maximum height: 200px (scrollable beyond)
 * - Submit button: Disabled when input is empty or loading
 * - Loading indicator: Animated spinner replaces send icon
 *
 * @example
 * ```tsx
 * import { MessageInput } from './MessageInput';
 *
 * function ChatInterface() {
 *   const [isLoading, setIsLoading] = useState(false);
 *
 *   const handleSend = async (message: string) => {
 *     setIsLoading(true);
 *     await sendToAgent(message);
 *     setIsLoading(false);
 *   };
 *
 *   return (
 *     <div className="flex flex-col h-screen">
 *       <div className="flex-1 overflow-auto">
 *         {messages}
 *       </div>
 *       <MessageInput onSend={handleSend} isLoading={isLoading} />
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Custom placeholder
 * <MessageInput
 *   onSend={handleSend}
 *   isLoading={false}
 *   placeholder="Type your query here..."
 * />
 * ```
 */
export function MessageInput({
  onSend,
  isLoading,
  placeholder = 'Ask a question about your data...',
}: MessageInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /**
   * Handles message submission.
   *
   * @remarks
   * Trims whitespace, validates non-empty input, calls parent's onSend callback,
   * clears the input field, and resets textarea height to single line.
   *
   * Does nothing if input is empty or isLoading is true.
   */
  const handleSubmit = () => {
    const trimmed = input.trim();
    if (trimmed && !isLoading) {
      onSend(trimmed);
      setInput('');
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  /**
   * Handles keyboard events in the textarea.
   *
   * @param e - Keyboard event from textarea
   *
   * @remarks
   * Detects Enter key press and submits the message if Shift is not held.
   * Prevents default behavior (new line) when submitting.
   *
   * **Behavior**:
   * - `Enter` alone: Submit message (calls handleSubmit)
   * - `Shift+Enter`: Insert new line (default behavior, not prevented)
   */
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  /**
   * Handles textarea input and auto-resizes height.
   *
   * @remarks
   * Adjusts textarea height dynamically based on content, capped at 200px maximum.
   *
   * **Algorithm**:
   * 1. Reset height to 'auto' (allows shrinking)
   * 2. Read actual content height from scrollHeight
   * 3. Set height to minimum of scrollHeight and 200px
   * 4. Result: Grows with content, scrollable if exceeds 200px
   */
  const handleInput = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  };

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder={placeholder}
            disabled={isLoading}
            rows={1}
            className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50 disabled:bg-gray-50"
            style={{ minHeight: '48px', maxHeight: '200px' }}
          />
        </div>
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading}
          className="flex items-center justify-center w-12 h-12 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </div>
      <p className="text-xs text-gray-400 text-center mt-2">
        Press Enter to send, Shift+Enter for new line
      </p>
    </div>
  );
}
