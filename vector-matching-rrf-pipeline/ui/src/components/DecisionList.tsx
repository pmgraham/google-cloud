// @ts-nocheck
import React, { ReactNode, useState } from 'react';
import { AgentDecision } from '../types';
import { HelpCircle, FileQuestion, ChevronDown, ChevronRight } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '../lib/utils';

interface DecisionListProps {
  decisions: AgentDecision[];
  selectedId: string | null;
  selectedCustomerPart?: string;
  viewMode?: 'single' | 'grouped';
  onSelect: (id: string) => void;
  decisionFilter?: string;
}

export function DecisionList({ decisions, selectedId, selectedCustomerPart, viewMode = 'single', onSelect, decisionFilter }: DecisionListProps) {
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [defaultCollapsed, setDefaultCollapsed] = useState<boolean>(false);

  const toggleGroup = (customerPart: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsedGroups(prev => {
      const current = customerPart in prev ? prev[customerPart] : defaultCollapsed;
      return {
        ...prev,
        [customerPart]: !current
      };
    });
  };

  const groupedDecisions = decisions.reduce((acc, decision) => {
    const key = decision.customer_part_number;
    if (!acc[key]) acc[key] = [];
    acc[key].push(decision);
    return acc;
  }, {} as Record<string, AgentDecision[]>);
  
  const groupKeys = Object.keys(groupedDecisions).sort((a, b) => a.localeCompare(b));
  
  const expandAll = () => {
    setDefaultCollapsed(false);
    setCollapsedGroups({});
  };
  const collapseAll = () => {
    setDefaultCollapsed(true);
    setCollapsedGroups({});
  };

  return (
    <div className="flex flex-col h-full">
      {groupKeys.length > 0 && (
        <div className="flex items-center justify-end gap-2 p-2 bg-zinc-50 border-b border-zinc-200 shrink-0">
          <button 
            onClick={expandAll}
            className="text-xs font-medium text-zinc-500 hover:text-indigo-600 transition-colors px-2 py-1 rounded hover:bg-indigo-50"
          >
            Expand All
          </button>
          <button 
            onClick={collapseAll}
            className="text-xs font-medium text-zinc-500 hover:text-indigo-600 transition-colors px-2 py-1 rounded hover:bg-indigo-50"
          >
            Collapse All
          </button>
        </div>
      )}
      <div className="divide-y divide-zinc-200 pb-12 overflow-y-auto">
      {Object.entries(groupedDecisions).map(([customerPart, group]) => {
        const isCollapsed = customerPart in collapsedGroups ? collapsedGroups[customerPart] : defaultCollapsed;
        const filteredGroup = decisionFilter ? group.filter(d => d.decision === decisionFilter) : group;
        return (
        <div key={customerPart} className="relative bg-white border-b border-zinc-200 last:border-0">
          <div 
            className={cn(
               "px-4 py-2 sticky top-0 z-10 border-b flex items-center justify-between cursor-pointer transition-colors",
               viewMode === 'grouped' && customerPart === selectedCustomerPart
                 ? "bg-indigo-50/90 backdrop-blur-sm border-indigo-200"
                 : "bg-zinc-100/95 backdrop-blur-sm border-zinc-200 hover:bg-zinc-200/50"
            )}
            onClick={(e) => toggleGroup(customerPart, e)}
          >
            <div className="flex items-center gap-1.5">
              {isCollapsed ? <ChevronRight size={14} className="text-zinc-400" /> : <ChevronDown size={14} className="text-zinc-400" />}
              <span className="text-xs font-semibold text-zinc-600 uppercase tracking-wider">{customerPart}</span>
            </div>
            <span className="bg-white text-zinc-500 px-2 py-0.5 rounded-full text-[10px] font-medium border border-zinc-200/60 shadow-sm">
              {filteredGroup.length} {filteredGroup.length === 1 ? 'match' : 'matches'}
            </span>
          </div>
          {!isCollapsed && (
            <div className="divide-y divide-zinc-100">
              {filteredGroup.length === 0 ? (
                <div className="p-4 text-sm text-zinc-500 italic text-center">
                  No matches found for this filter.
                </div>
              ) : (
                filteredGroup.sort((a, b) => {
                  const mfgCompare = (a.supplier_manufacturer || '').localeCompare(b.supplier_manufacturer || '');
                  if (mfgCompare !== 0) return mfgCompare;
                  return (a.supplier_part_number || '').localeCompare(b.supplier_part_number || '');
                }).map((decision) => {
                  const isSelected = decision.id === selectedId;
                  const isAutoApproved = decision.reasoning?.includes('Auto-approved');
                  
                  return (
                    <button
                      key={decision.id}
                      onClick={() => onSelect(decision.id)}
                      className={cn(
                        "w-full text-left p-4 transition-all hover:bg-zinc-50 focus:outline-none",
                        isSelected ? "bg-indigo-50/50 ring-1 ring-inset ring-indigo-500/20" : ""
                      )}
                    >
                      <div className="flex justify-between items-start mb-1 gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <StatusIcon decision={decision.decision} isMatch={decision.is_match} />
                          <span className="font-mono text-sm font-medium text-zinc-900 truncate">
                            {decision.supplier_part_number || "No Match"}
                          </span>
                        </div>
                        <span className="text-[10px] text-zinc-400 uppercase tracking-wider font-medium shrink-0 pt-0.5">
                          {decision.created_at ? formatDistanceToNow(new Date(decision.created_at), { addSuffix: true }) : ''}
                        </span>
                      </div>
                      
                      <div className="pl-6">
                        <p className="text-xs text-zinc-500 truncate mb-2">
                          {decision.supplier_description || decision.customer_description || "Unknown part"}
                        </p>
                        
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "text-[10px] px-2 py-0.5 rounded-full font-medium border",
                            decision.is_human_reviewed 
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : isAutoApproved
                                ? "bg-blue-50 text-blue-700 border-blue-200"
                                : "bg-amber-50 text-amber-700 border-amber-200"
                          )}>
                            {decision.is_human_reviewed ? 'Reviewed' : isAutoApproved ? 'Auto Approved' : 'Pending'}
                          </span>
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
            )}
          </div>
        );
      })}
      </div>
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
