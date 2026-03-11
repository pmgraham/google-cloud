import { useState, useEffect } from 'react';
import { AgentDecision } from './types';
import { api } from './api';
import { DecisionList } from './components/DecisionList';
import { DecisionDetail } from './components/DecisionDetail';
import { LayoutTemplate, Search, Filter } from 'lucide-react';

export default function App() {
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'reviewed'>('pending');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDecisions();
  }, [statusFilter, searchQuery]);

  const loadDecisions = async () => {
    setIsLoading(true);
    try {
      const data = await api.getDecisions(statusFilter, searchQuery);
      setDecisions(data);
      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].id);
      } else if (data.length === 0) {
        setSelectedId(null);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdate = async (id: number, updates: Partial<AgentDecision>) => {
    try {
      const updated = await api.updateDecision(id, updates);
      setDecisions(prev => prev.map(d => d.id === id ? { ...d, ...updated } : d));
      
      // If we're filtering by pending and we just reviewed it, it might disappear from the list.
      // We could automatically select the next one.
      if (statusFilter === 'pending' && updates.is_human_reviewed) {
        const currentIndex = decisions.findIndex(d => d.id === id);
        if (currentIndex < decisions.length - 1) {
          setSelectedId(decisions[currentIndex + 1].id);
        } else if (currentIndex > 0) {
          setSelectedId(decisions[currentIndex - 1].id);
        } else {
          setSelectedId(null);
        }
        // Reload to remove from list
        loadDecisions();
      }
    } catch (error) {
      console.error(error);
    }
  };

  const selectedDecision = decisions.find(d => d.id === selectedId) || null;

  return (
    <div className="flex h-screen bg-zinc-50 text-zinc-900 font-sans overflow-hidden">
      {/* Sidebar / List Pane */}
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
              {(['pending', 'reviewed', 'all'] as const).map(status => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`flex-1 text-xs font-medium py-1.5 px-3 rounded-md capitalize transition-colors ${
                    statusFilter === status 
                      ? 'bg-white text-zinc-900 shadow-sm' 
                      : 'text-zinc-500 hover:text-zinc-700'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-8 text-center text-zinc-500 text-sm">Loading decisions...</div>
          ) : decisions.length === 0 ? (
            <div className="p-8 text-center text-zinc-500 text-sm">No decisions found.</div>
          ) : (
            <DecisionList 
              decisions={decisions} 
              selectedId={selectedId} 
              onSelect={setSelectedId} 
            />
          )}
        </div>
      </div>

      {/* Detail Pane */}
      <div className="flex-1 bg-zinc-50 flex flex-col overflow-hidden">
        {selectedDecision ? (
          <DecisionDetail 
            decision={selectedDecision} 
            onUpdate={(updates) => handleUpdate(selectedDecision.id, updates)} 
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
