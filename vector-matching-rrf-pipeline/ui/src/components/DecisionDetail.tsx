// @ts-nocheck
import React, { ReactNode, useEffect } from 'react';
import { AgentDecision } from '../types';
import { Check, X, AlertTriangle, ArrowRightLeft, Factory, Tag, DollarSign, Bot } from 'lucide-react';
import { cn } from '../lib/utils';

interface DecisionDetailProps {
  decision: AgentDecision;
  groupCandidates?: AgentDecision[];
  viewMode?: 'single' | 'grouped';
  onViewModeChange?: (mode: 'single' | 'grouped') => void;
  onUpdate: (id: string, updates: Partial<AgentDecision>) => void;
  decisionFilter?: string;
}

export function DecisionDetail({ decision, groupCandidates, viewMode = 'single', onViewModeChange, onUpdate, decisionFilter }: DecisionDetailProps) {
  
  // Auto-scroll to selected candidate when viewMode is grouped
  useEffect(() => {
    if (viewMode === 'grouped' && decision?.id) {
      const element = document.getElementById(`candidate-${decision.id}`);
      if (element) {
        // Add a small delay to ensure rendering is complete before scrolling
        setTimeout(() => {
          // Get the scrolling container (the flex-1 overflow-y-auto div)
          const container = element.closest('.overflow-y-auto');
          if (container) {
            // Calculate the offset to align the candidate card perfectly with the top sticky Customer Part card
            // The sticky Element has top-6 (24px) + mt-[40px] (40px) = 64px from top of container
            const containerRect = container.getBoundingClientRect();
            const elementRect = element.getBoundingClientRect();
            const relativeTop = elementRect.top - containerRect.top + container.scrollTop;
            
            // Scroll the container so the candidate card aligns with the top of the sticky customer card
            // We want the element to sit exactly at the sticky point + margin = 64px from container top
            container.scrollTo({
              top: relativeTop - 64,
              behavior: 'smooth'
            });
          }
          
          // Add a temporary highlight effect
          element.classList.add('ring-2', 'ring-indigo-500', 'ring-offset-2', 'transition-all', 'duration-500');
          setTimeout(() => {
            element.classList.remove('ring-2', 'ring-indigo-500', 'ring-offset-2');
          }, 1500);
        }, 50);
      }
    }
  }, [decision.id, viewMode]);

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
        
        <div className="flex items-center gap-4">
          <div className="flex bg-zinc-100 p-1 rounded-lg border border-zinc-200/50">
            <button 
              onClick={() => onViewModeChange?.('single')}
              className={cn("text-xs font-medium py-1 px-3 rounded-md transition-colors", viewMode === 'single' ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700')}
            >
              Single Match
            </button>
            <button 
              onClick={() => onViewModeChange?.('grouped')}
              className={cn("text-xs font-medium py-1 px-3 rounded-md transition-colors", viewMode === 'grouped' ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700')}
            >
              All Candidates
            </button>
          </div>

          {decision.is_human_reviewed && (
            <button 
              onClick={() => onUpdate(decision.id, { is_human_reviewed: false })}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-zinc-600 bg-white hover:bg-zinc-50 rounded-lg transition-colors border border-zinc-200 shadow-sm"
            >
              <AlertTriangle size={16} /> Needs Review
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {viewMode === 'single' ? (
          <div className="max-w-4xl mx-auto space-y-6">
            
            {/* AI Reasoning Card */}
            <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
              <div className="bg-zinc-50/80 border-b border-zinc-200 px-4 py-3 flex items-center gap-2">
                <Bot size={18} className="text-indigo-600" />
                <h3 className="font-medium text-sm text-zinc-900">AI Agent Analysis</h3>
                <span className="ml-auto text-xs font-mono bg-white px-2 py-1 rounded border border-zinc-200 text-zinc-500">
                  {decision.decision === 'REQUIRES_HUMAN_REVIEW' ? 'Human Review Required' : decision.decision}
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
                    <React.Fragment>
                      <InfoRow icon={<Tag size={16} />} label="Description" value={decision.supplier_description} />
                      <InfoRow icon={<Factory size={16} />} label="Manufacturer" value={decision.supplier_manufacturer} />
                      <InfoRow icon={<Tag size={16} />} label="Category" value={decision.supplier_category} />
                      <InfoRow icon={<DollarSign size={16} />} label="Price" value={decision.supplier_price ? `$${decision.supplier_price?.toFixed(2)}` : undefined} />
                    </React.Fragment>
                  ) : (
                    <div className="h-full flex items-center justify-center text-sm text-zinc-400 italic">
                      No supplier part was matched by the agent.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-6xl mx-auto flex gap-8 items-start relative pb-12">
            {/* Left Column: Customer Part */}
            <div className="w-1/3 flex flex-col sticky top-6">
              <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden flex flex-col mt-[40px]">
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
            </div>

            {/* Right Column: Stacked Candidates */}
            <div className="w-2/3 space-y-6 pb-12">
              <div className="flex items-center gap-2 mb-6">
                <h3 className="font-semibold text-lg text-zinc-900">Candidate Matches</h3>
                <span className="bg-zinc-100 text-zinc-600 px-2.5 py-0.5 rounded-full text-xs font-medium border border-zinc-200">
                  {groupCandidates?.length || 0}
                </span>
              </div>
              
              {(groupCandidates?.filter(c => !decisionFilter || c.decision === decisionFilter).sort((a, b) => {
                const mfgCompare = (a.supplier_manufacturer || '').localeCompare(b.supplier_manufacturer || '');
                if (mfgCompare !== 0) return mfgCompare;
                return (a.supplier_part_number || '').localeCompare(b.supplier_part_number || '');
              }) || []).map(candidate => {
                const candidateAutoApproved = candidate.reasoning?.includes('Auto-approved');
                // Use a ref-able ID for scrolling
                return (
                  <div id={`candidate-${candidate.id}`} key={candidate.id} className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden flex flex-col scroll-mt-24">
                    <div className="bg-zinc-50/80 border-b border-zinc-200 px-4 py-3 flex items-center justify-between">
                      <div>
                        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Matched Supplier Part</h3>
                        <div className="font-mono text-lg font-medium text-zinc-900 mt-1 flex items-center gap-2">
                          {candidate.supplier_part_number || "No Match Found"}
                          {candidate.is_human_reviewed ? (
                            <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] px-2 py-0.5 rounded-full font-medium ml-2">Reviewed</span>
                          ) : candidateAutoApproved && (
                            <span className="bg-blue-50 text-blue-700 border border-blue-200 text-[10px] px-2 py-0.5 rounded-full font-medium ml-2">Auto Approved</span>
                          )}
                        </div>
                      </div>
                      
                      {/* Inline Agent Analysis for Candidate */}
                      <div className="flex items-center gap-2 text-right">
                          <div className="flex flex-col items-end">
                            <div className="flex items-center gap-1.5 mb-1">
                              <Bot size={14} className="text-indigo-600" />
                              <span className="text-xs font-medium text-zinc-700">Agent Analysis</span>
                            </div>
                            <span className="text-[10px] font-mono bg-white px-2 py-0.5 rounded border border-zinc-200 text-zinc-500">
                              {candidate.decision === 'REQUIRES_HUMAN_REVIEW' ? 'Human Review Required' : candidate.decision}
                            </span>
                          </div>
                      </div>
                    </div>
                    <div className="p-4 flex-1 space-y-4">
                      {candidate.supplier_part_number ? (
                        <React.Fragment>
                          <InfoRow icon={<Tag size={16} />} label="Description" value={candidate.supplier_description} />
                          <InfoRow icon={<Factory size={16} />} label="Manufacturer" value={candidate.supplier_manufacturer} />
                          <InfoRow icon={<Tag size={16} />} label="Category" value={candidate.supplier_category} />
                          <InfoRow icon={<DollarSign size={16} />} label="Price" value={candidate.supplier_price ? `$${candidate.supplier_price.toFixed(2)}` : undefined} />
                          
                          <div className="mt-4 pt-4 border-t border-zinc-100">
                            <p className="text-xs text-zinc-500 bg-zinc-50 p-3 rounded-lg border border-zinc-100 italic leading-relaxed">"{candidate.reasoning}"</p>
                          </div>

                          {!candidate.is_human_reviewed && (
                            <div className="mt-6 flex items-center justify-end gap-3">
                              <button 
                                onClick={() => onUpdate(candidate.id, { is_human_reviewed: true, is_match: false, decision: 'Human Rejected' })}
                                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-rose-600 bg-rose-50 hover:bg-rose-100 rounded-lg transition-colors border border-rose-200"
                              >
                                <X size={16} /> Reject Match
                              </button>
                              <button 
                                onClick={() => onUpdate(candidate.id, { is_human_reviewed: true, is_match: true, decision: 'Human Confirmed' })}
                                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors shadow-sm"
                              >
                                <Check size={16} /> Confirm Match
                              </button>
                            </div>
                          )}
                        </React.Fragment>
                      ) : (
                        <div className="h-full flex items-center justify-center text-sm text-zinc-400 italic py-8">
                          No supplier part was matched by the agent.
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
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
