import { AgentDecision } from "./types";

export const api = {
  async getDecisions(status?: string, search?: string, page: number = 1): Promise<AgentDecision[]> {
    const params = new URLSearchParams();
    if (status && status !== 'all') params.append('status', status);
    if (search) params.append('search', search);
    params.append('page', page.toString());
    
    const res = await fetch(`/api/decisions?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch decisions");
    return res.json();
  },

  async updateDecision(id: string, updates: Partial<AgentDecision> & { undo_review?: boolean }): Promise<AgentDecision> {
    const res = await fetch(`/api/decisions/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error("Failed to update decision");
    return res.json();
  },

  async getCandidatesByCustomerPart(customerPart: string): Promise<AgentDecision[]> {
    const res = await fetch(`/api/decisions/customer/${encodeURIComponent(customerPart)}`);
    if (!res.ok) throw new Error("Failed to fetch candidates");
    return res.json();
  }
};
