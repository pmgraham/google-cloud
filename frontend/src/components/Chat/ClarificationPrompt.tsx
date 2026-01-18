import { HelpCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { ClarifyingQuestion } from '../../types';

interface ClarificationPromptProps {
  question: ClarifyingQuestion;
  onSelect: (option: string) => void;
}

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
