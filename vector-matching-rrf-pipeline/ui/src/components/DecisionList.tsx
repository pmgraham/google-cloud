import { AgentDecision } from '../types';
import { CheckCircle2, AlertCircle, HelpCircle, FileQuestion } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '../lib/utils';

interface DecisionListProps {
  decisions: AgentDecision[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function DecisionList({ decisions, selectedId, onSelect }: DecisionListProps) {
  return (
    <div className="divide-y divide-zinc-100">
      {decisions.map((decision) => {
        const isSelected = decision.id === selectedId;
        
        return (
          <button
            key={decision.id}
            onClick={() => onSelect(decision.id)}
            className={cn(
              "w-full text-left p-4 transition-all hover:bg-zinc-50 focus:outline-none",
              isSelected ? "bg-indigo-50/50 ring-1 ring-inset ring-indigo-500/20" : ""
            )}
          >
            <div className="flex justify-between items-start mb-1">
              <div className="flex items-center gap-2">
                <StatusIcon decision={decision.decision} isMatch={decision.is_match} />
                <span className="font-mono text-sm font-medium text-zinc-900">
                  {decision.customer_part_number}
                </span>
              </div>
              <span className="text-[10px] text-zinc-400 uppercase tracking-wider font-medium">
                {formatDistanceToNow(new Date(decision.created_at), { addSuffix: true })}
              </span>
            </div>
            
            <div className="pl-6">
              <p className="text-xs text-zinc-500 truncate mb-2">
                {decision.customer_description || "Unknown part"}
              </p>
              
              <div className="flex items-center gap-2">
                <span className={cn(
                  "text-[10px] px-2 py-0.5 rounded-full font-medium border",
                  decision.is_human_reviewed 
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-amber-50 text-amber-700 border-amber-200"
                )}>
                  {decision.is_human_reviewed ? 'Reviewed' : 'Pending'}
                </span>
                
                {decision.supplier_part_number && (
                  <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                    â <span className="font-mono">{decision.supplier_part_number}</span>
                  </span>
                )}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function StatusIcon({ decision, isMatch }: { decision: string, isMatch: boolean }) {
  if (decision.includes('High Confidence') && isMatch) {
    return <CheckCircle2 size={16} className="text-emerald-500" />;
  }
  if (decision.includes('Ambiguous')) {
    return <HelpCircle size={16} className="text-amber-500" />;
  }
  if (!isMatch) {
    return <AlertCircle size={16} className="text-rose-500" />;
  }
  return <FileQuestion size={16} className="text-zinc-400" />;
}
