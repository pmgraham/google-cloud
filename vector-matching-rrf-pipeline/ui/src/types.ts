export interface PartInfo {
  part_number: string;
  description: string;
  manufacturer: string;
  category: string;
  price: number;
}

export interface AgentDecision {
  id: number;
  customer_part_number: string;
  decision: string;
  is_match: boolean;
  supplier_part_number: string | null;
  reasoning: string;
  is_human_reviewed: boolean;
  created_at: string;
  updated_at: string;
  
  // Joined fields
  customer_description?: string;
  customer_manufacturer?: string;
  customer_category?: string;
  supplier_description?: string;
  supplier_manufacturer?: string;
  supplier_category?: string;
  supplier_price?: number;
}
