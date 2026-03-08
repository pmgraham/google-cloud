import { HelpCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { ClarifyingQuestion } from '../../types';

/**
 * Props for the ClarificationPrompt component.
 *
 * @remarks
 * Defines the clarifying question data and selection callback.
 */
interface ClarificationPromptProps {
  /** Clarifying question object with question text, optional context, and selectable options */
  question: ClarifyingQuestion;
  /** Callback invoked when user selects an option (passes the selected option string) */
  onSelect: (option: string) => void;
}

/**
 * Clarification prompt component that displays agent-generated questions with selectable options.
 *
 * @param props - Component props
 * @returns Clarification UI with question and option buttons, or null if no options
 *
 * @remarks
 * **Interactive prompt component** displayed when the AI agent needs clarification
 * to better understand the user's request.
 *
 * **Features**:
 * - **Question display**: Renders question text with markdown support
 * - **Optional context**: Shows additional context/explanation below question
 * - **Selectable options**: Clickable buttons for each option
 * - **Markdown support**: All text (question, context, options) rendered with ReactMarkdown
 * - **Amber styling**: Visually distinct from regular messages
 *
 * **Data Structure**:
 * ClarifyingQuestion contains:
 * - `question`: Main question text (markdown)
 * - `context`: Optional explanatory text (markdown)
 * - `options`: Array of selectable option strings (markdown)
 *
 * **Behavior**:
 * - Returns `null` if `options` array is empty or undefined
 * - Clicking an option calls `onSelect(option)` which typically sends the option as a new message
 * - Options wrap to multiple lines on narrow screens
 *
 * **Visual Design**:
 * - Amber background (`bg-amber-50`) and border (`border-amber-200`)
 * - Help icon to indicate it's a question
 * - Pills for options with hover state
 *
 * @example
 * ```tsx
 * import { ClarificationPrompt } from './ClarificationPrompt';
 *
 * function MessageContent({ message }: { message: ChatMessage }) {
 *   const handleSelectOption = (option: string) => {
 *     sendMessage(option);  // Send selected option as new message
 *   };
 *
 *   return (
 *     <div>
 *       <p>{message.content}</p>
 *       {message.clarifying_question && (
 *         <ClarificationPrompt
 *           question={message.clarifying_question}
 *           onSelect={handleSelectOption}
 *         />
 *       )}
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Example ClarifyingQuestion object
 * const question: ClarifyingQuestion = {
 *   question: 'Which time period would you like to analyze?',
 *   context: 'I can show data for different timeframes to give you better insights.',
 *   options: [
 *     'Last 7 days',
 *     'Last 30 days',
 *     'Last quarter',
 *     'All time'
 *   ]
 * };
 *
 * <ClarificationPrompt question={question} onSelect={handleSelect} />
 * // Renders amber prompt with 4 selectable option pills
 * ```
 */
export function ClarificationPrompt({ question, onSelect }: ClarificationPromptProps) {
  if (!question.options || question.options.length === 0) {
    return null;
  }

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
      <div className="flex items-start gap-2 mb-3">
        <HelpCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
        <div className="text-sm text-amber-800 font-medium prose prose-sm prose-amber max-w-none">
          <ReactMarkdown>{question.question}</ReactMarkdown>
        </div>
      </div>

      {question.context && (
        <div className="text-xs text-amber-700 mb-3 ml-6 prose prose-xs prose-amber max-w-none">
          <ReactMarkdown>{question.context}</ReactMarkdown>
        </div>
      )}

      <div className="flex flex-wrap gap-2 ml-6">
        {question.options.map((option, idx) => (
          <button
            key={idx}
            onClick={() => onSelect(option)}
            className="px-3 py-1.5 text-sm bg-white border border-amber-300 text-amber-800 rounded-full hover:bg-amber-100 hover:border-amber-400 transition-colors text-left"
          >
            <span className="prose prose-sm prose-amber [&>*]:inline [&>*]:m-0">
              <ReactMarkdown>{option}</ReactMarkdown>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
