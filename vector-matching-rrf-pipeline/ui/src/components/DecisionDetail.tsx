import { ReactNode } from 'react';
import { AgentDecision } from '../types';
import { Check, X, AlertTriangle, ArrowRightLeft, Factory, Tag, DollarSign, Bot } from 'lucide-react';
import { cn } from '../lib/utils';

interface DecisionDetailProps {
  decision: AgentDecision;
  onUpdate: (updates: Partial<AgentDecision>) => void;
}

export function DecisionDetail({ decision, onUpdate }: DecisionDetailProps) {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header Actions */}
      <div className="bg-white border-b border-zinc-200 p-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-zinc-900">Match Review</h2>
          <span className={cn(
            "text-xs px-2.5 py-1 rounded-full font-medium border",
            decision.is_human_reviewed 
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : "bg-amber-50 text-amber-700 border-amber-200"
          )}>
            {decision.is_human_reviewed ? 'Reviewed' : 'Pending Review'}
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          {!decision.is_human_reviewed ? (
            <>
              <button 
                onClick={() => onUpdate({ is_human_reviewed: true, is_match: false, decision: 'Human Rejected' })}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-rose-600 bg-rose-50 hover:bg-rose-100 rounded-lg transition-colors border border-rose-200"
              >
                <X size={16} /> Reject Match
              </button>
              <button 
                onClick={() => onUpdate({ is_human_reviewed: true, is_match: true, decision: 'Human Confirmed' })}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors shadow-sm"
              >
                <Check size={16} /> Confirm Match
              </button>
            </>
          ) : (
            <button 
              onClick={() => onUpdate({ is_human_reviewed: false })}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-zinc-600 bg-white hover:bg-zinc-50 rounded-lg transition-colors border border-zinc-200 shadow-sm"
            >
              <AlertTriangle size={16} /> Needs Review
            </button>
          )}
        </div>
      </div>

      {/* Content Scroll Area */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          
          {/* AI Reasoning Card */}
          <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
            <div className="bg-zinc-50/80 border-b border-zinc-200 px-4 py-3 flex items-center gap-2">
              <Bot size={18} className="text-indigo-600" />
              <h3 className="font-medium text-sm text-zinc-900">AI Agent Analysis</h3>
              <span className="ml-auto text-xs font-mono bg-white px-2 py-1 rounded border border-zinc-200 text-zinc-500">
                {decision.decision}
              </span>
            </div>
            <div className="p-4">
              <p className="text-sm text-zinc-700 leading-relaxed">
                {decision.reasoning}
              </p>
            </div>
          </div>

          {/* Comparison Grid */}
          <div className="grid grid-cols-[1fr_auto_1fr] gap-4 items-stretch">
            {/* Customer Part */}
            <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden flex flex-col">
              <div className="bg-zinc-50/80 border-b border-zinc-200 px-4 py-3">
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Customer Part</h3>
                <div className="font-mono text-lg font-medium text-zinc-900 mt-1">
                  {decision.customer_part_number}
                </div>
              </div>
              <div className="p-4 flex-1 space-y-4">
                <InfoRow icon={<Tag size={16} />} label="Description" value={decision.customer_description} />
                <InfoRow icon={<Factory size={16} />} label="Manufacturer" value={decision.customer_manufacturer} />
                <InfoRow icon={<Tag size={16} />} label="Category" value={decision.customer_category} />
              </div>
            </div>

            {/* Divider */}
            <div className="flex flex-col items-center justify-center text-zinc-300 px-2">
              <div className="w-px h-full bg-zinc-200"></div>
              <div className="my-4 bg-white border border-zinc-200 rounded-full p-2 shadow-sm">
                <ArrowRightLeft size={20} className="text-zinc-400" />
              </div>
              <div className="w-px h-full bg-zinc-200"></div>
            </div>

            {/* Supplier Part */}
            <div className={cn(
              "bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col",
              decision.supplier_part_number ? "border-zinc-200" : "border-dashed border-zinc-300 bg-zinc-50/50"
            )}>
              <div className="bg-zinc-50/80 border-b border-zinc-200 px-4 py-3">
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Matched Supplier Part</h3>
                <div className="font-mono text-lg font-medium text-zinc-900 mt-1">
                  {decision.supplier_part_number || "No Match Found"}
                </div>
              </div>
              <div className="p-4 flex-1 space-y-4">
                {decision.supplier_part_number ? (
                  <>
                    <InfoRow icon={<Tag size={16} />} label="Description" value={decision.supplier_description} />
                    <InfoRow icon={<Factory size={16} />} label="Manufacturer" value={decision.supplier_manufacturer} />
                    <InfoRow icon={<Tag size={16} />} label="Category" value={decision.supplier_category} />
                    <InfoRow icon={<DollarSign size={16} />} label="Price" value={decision.supplier_price ? `$${decision.supplier_price.toFixed(2)}` : undefined} />
                  </>
                ) : (
                  <div className="h-full flex items-center justify-center text-sm text-zinc-400 italic">
                    No supplier part was matched by the agent.
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function InfoRow({ icon, label, value }: { icon: ReactNode, label: string, value?: string | number }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 mb-1">
        {icon} {label}
      </div>
      <div className="text-sm text-zinc-900">
        {value || <span className="text-zinc-400 italic">Not specified</span>}
      </div>
    </div>
  );
}
