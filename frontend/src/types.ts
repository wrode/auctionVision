export interface LotCard {
  id: string;
  title: string;
  current_bid?: number;
  estimate_min?: number;
  estimate_max?: number;
  auction_end_time?: string;
  image_url?: string;
  source: string;
  source_url?: string;
  arbitrage_score?: number;
  norway_gap_score?: number;
  taste_score?: number;
  wildcard_score?: number;
  taste_category?: 'core' | 'adjacent' | 'exploratory';
  risk_flags?: string[];
  rationale?: string;
  watched?: boolean;
  archived?: boolean;
}

export interface LotDetail extends LotCard {
  description?: string;
  condition?: string;
  lot_number?: string;
  hammer_price?: number;
  buyer_premium?: number;
  shipping_cost?: number;
  total_cost?: number;
  dimensions?: {
    height?: number;
    width?: number;
    depth?: number;
    unit?: string;
  };
  material?: string;
  artist?: string;
  provenance?: string;
  authenticity?: string;
  normalized_fields?: Record<string, any>;
  agent_enrichment?: EnrichmentOutput[];
  score_breakdown?: LotScores;
  fetch_history?: FetchRecord[];
  user_actions?: UserAction[];
  gallery_images?: string[];
}

export interface LotScores {
  arbitrage_score?: {
    value: number;
    rationale: string;
  };
  norway_gap_score?: {
    value: number;
    rationale: string;
    gap_pct?: number;
  };
  taste_score?: {
    value: number;
    rationale: string;
    category?: string;
  };
  wildcard_score?: {
    value: number;
    rationale: string;
  };
}

export interface EnrichmentOutput {
  agent: string;
  output: string;
  timestamp?: string;
}

export interface FetchRecord {
  timestamp: string;
  action: string;
  details?: string;
}

export interface UserAction {
  action: 'star' | 'skip' | 'watch' | 'archive' | 'note';
  timestamp: string;
  value?: string;
}

export interface ViewResponse {
  view_name: string;
  lots: LotCard[];
  lot_count: number;
  last_refreshed: string;
  filters?: Record<string, any>;
}

export interface FetchParams {
  limit?: number;
  offset?: number;
  sort_by?: string;
  filters?: Record<string, any>;
}

export interface ActionPayload {
  action: 'star' | 'skip' | 'watch' | 'archive' | 'note';
  value?: string;
}

export interface JobRequest {
  job_type: string;
  params?: Record<string, any>;
}

export interface JobResponse {
  job_id: string;
  status: string;
  message: string;
}
