import { AgentDecision } from "./types";

export const api = {
  async getDecisions(status?: 'all' | 'pending' | 'reviewed', search?: string): Promise<AgentDecision[]> {
    const params = new URLSearchParams();
    if (status && status !== 'all') params.append('status', status);
    if (search) params.append('search', search);
    
    const res = await fetch(`/api/decisions?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch decisions");
    return res.json();
  },

  async updateDecision(id: number, updates: Partial<AgentDecision>): Promise<AgentDecision> {
    const res = await fetch(`/api/decisions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error("Failed to update decision");
    return res.json();
  }
};
