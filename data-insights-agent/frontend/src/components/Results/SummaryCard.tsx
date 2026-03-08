import { MessageSquare } from 'lucide-react';

interface SummaryCardProps {
  summary: string;
}

export function SummaryCard({ summary }: SummaryCardProps) {
  return (
    <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
          <MessageSquare className="w-4 h-4 text-primary-600" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-primary-900 mb-1">Summary</h4>
          <p className="text-sm text-primary-800 leading-relaxed">{summary}</p>
        </div>
      </div>
    </div>
  );
}
