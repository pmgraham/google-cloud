import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AgentDecision } from './types';
import { api } from './api';
import { DecisionList } from './components/DecisionList';
import { DecisionDetail } from './components/DecisionDetail';
import { LayoutTemplate, Search, Filter } from 'lucide-react';

export default function App() {
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [candidateGroup, setCandidateGroup] = useState<AgentDecision[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'single' | 'grouped'>('single');
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [decisionFilter, setDecisionFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  
  const observer = useRef<IntersectionObserver | null>(null);

  const lastElementRef = useCallback((node: HTMLDivElement) => {
    if (isLoading) return;
    if (observer.current) observer.current.disconnect();
    observer.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasMore) {
        setPage(prevPage => prevPage + 1);
      }
    });
    if (node) observer.current.observe(node);
  }, [isLoading, hasMore]);

  useEffect(() => {
    setDecisions([]);
    setPage(1);
    setHasMore(true);
    loadDecisions(1, statusFilter, searchQuery, true);
  }, [statusFilter, searchQuery]);

  useEffect(() => {
    if (page > 1) {
      loadDecisions(page, statusFilter, searchQuery, false);
    }
  }, [page]);

  const loadDecisions = async (currentPage: number, currentStatus: string, currentSearch: string, isReset: boolean) => {
    setIsLoading(true);
    try {
      const data = await api.getDecisions(currentStatus, currentSearch, currentPage);
      
      setDecisions(prev => {
        if (isReset) return data;
        const existingKeys = new Set(prev.map(d => `${d.id}-${d.decision}`));
        const newItems = data.filter(d => !existingKeys.has(`${d.id}-${d.decision}`));
        return [...prev, ...newItems];
      });
      
      setHasMore(data.length === 50);
      
      if (isReset && data.length > 0) {
        handleSelect(data[0].id);
      } else if (isReset && data.length === 0) {
        setSelectedId(null);
        setCandidateGroup([]);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdate = async (id: string, updates: Partial<AgentDecision> & { undo_review?: boolean }) => {
    try {
      const updated = await api.updateDecision(id, updates);
      
      if (!updated) return;
      
      if ((statusFilter === 'pending' && updates.is_human_reviewed) || 
          (statusFilter === 'reviewed' && updates.undo_review)) {
        const currentIndex = decisions.findIndex(d => d.id === id);
        if (currentIndex < decisions.length - 1) {
          setSelectedId(decisions[currentIndex + 1].id);
        } else if (currentIndex > 0) {
          setSelectedId(decisions[currentIndex - 1].id);
        } else {
          setSelectedId(null);
        }
        setDecisions(prev => prev.filter(d => d.id !== id));
      } else {
        setDecisions(prev => prev.map(d => d.id === id ? { ...d, ...updated } : d));
      }
      setCandidateGroup(prev => prev.map(d => d.id === id ? { ...d, ...updated } : d));
    } catch (error) {
      console.error(error);
    }
  };

  const handleSelect = async (id: string) => {
    setSelectedId(id);
    const customerPart = id.split('|')[0];
    try {
      const data = await api.getCandidatesByCustomerPart(customerPart);
      if (data && data.length > 0) {
        setCandidateGroup(data);
        setDecisions(prev => prev.map(d => {
          const updatedItem = data.find(item => item.id === d.id);
          return updatedItem ? { ...d, ...updatedItem } : d;
        }));
      } else {
        setCandidateGroup([]);
      }
    } catch (e) {
      console.error(e);
      setCandidateGroup([]);
    }
  };

  const selectedDecision = decisions.find(d => d.id === selectedId) || candidateGroup.find(d => d.id === selectedId) || null;

  return (
    <div className="flex h-screen bg-zinc-50 text-zinc-900 font-sans overflow-hidden">
      <div className="w-1/3 min-w-[350px] max-w-[500px] border-r border-zinc-200 bg-white flex flex-col">
        <div className="p-4 border-b border-zinc-200 bg-zinc-50/50">
          <div className="flex items-center gap-2 mb-4">
            <div className="p-1.5 bg-indigo-100 text-indigo-600 rounded-md">
              <LayoutTemplate size={20} />
            </div>
            <h1 className="font-semibold text-lg tracking-tight">Match Review</h1>
          </div>
          
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" size={16} />
            <input 
              type="text" 
              placeholder="Search parts or descriptions..." 
              className="w-full pl-9 pr-4 py-2 bg-white border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter size={14} className="text-zinc-500" />
            <div className="flex bg-zinc-100 p-1 rounded-lg w-full">
              {['pending', 'reviewed', 'auto_approved', 'all'].map(status => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`flex-1 text-xs font-medium py-1.5 px-3 rounded-md capitalize transition-colors ${
                    statusFilter === status 
                      ? 'bg-white text-zinc-900 shadow-sm' 
                      : 'text-zinc-500 hover:text-zinc-700'
                  }`}
                >
                  {status.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          {statusFilter === 'pending' && (
            <div className="mt-3 flex items-center gap-2">
              <div className="w-[14px] flex justify-center">
                <Filter size={14} className="text-zinc-400" />
              </div>
              <select
                className="w-full text-xs font-medium py-1.5 px-2 bg-white border border-zinc-200 rounded-md text-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all cursor-pointer"
                value={decisionFilter}
                onChange={(e) => setDecisionFilter(e.target.value)}
              >
                <option value="">All Pending Decisions</option>
                <option value="MATCH">AI Match</option>
                <option value="NO_MATCH">AI No Match</option>
                <option value="REQUIRES_HUMAN_REVIEW">Review Needed</option>
              </select>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading && decisions.length === 0 ? (
            <div className="p-8 text-center text-zinc-500 text-sm">Loading decisions...</div>
          ) : decisions.length === 0 ? (
            <div className="p-8 text-center text-zinc-500 text-sm">No decisions found.</div>
          ) : (
            <>
                <DecisionList 
                  decisions={decisions} 
                  selectedId={selectedId} 
                  selectedCustomerPart={selectedDecision?.customer_part_number}
                  viewMode={viewMode}
                  onSelect={handleSelect} 
                  decisionFilter={decisionFilter}
                  onUpdate={handleUpdate}
                />
              {hasMore && (
                <div ref={lastElementRef} className="py-4 text-center text-zinc-400 text-sm">
                  {isLoading ? "Loading more..." : "Scroll for more"}
                </div>
              )}
              {!hasMore && decisions.length > 0 && (
                <div className="py-8 text-center text-zinc-400 text-sm border-t border-zinc-200">
                  End of records
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="flex-1 bg-zinc-50 flex flex-col overflow-hidden">
        {selectedDecision ? (
          <DecisionDetail 
            decision={selectedDecision} 
            groupCandidates={candidateGroup}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onUpdate={handleUpdate}
            decisionFilter={statusFilter === 'pending' ? decisionFilter : ''}
            statusFilter={statusFilter}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-zinc-400 flex-col gap-4">
            <LayoutTemplate size={48} className="opacity-20" />
            <p>Select a decision to review</p>
          </div>
        )}
      </div>
    </div>
  );
}
