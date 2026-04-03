export interface LotCard {
  id: number;
  title: string;
  current_bid?: number | null;
  current_bid_updated_at?: string | null;
  bid_count?: number | null;
  estimate_low?: number | null;
  estimate_high?: number | null;
  currency?: string;
  auction_end_time?: string | null;
  time_remaining?: string | null;
  image_url?: string | null;
  source: string;
  lot_url?: string | null;
  labels?: string[];
  scores: {
    arbitrage?: number | null;
    taste?: number | null;
    wildcard?: number | null;
    urgency?: number | null;
    demand?: number | null;
  };
  ai_value_low?: number | null;
  ai_value_high?: number | null;
  ai_value_basis?: string | null;
  estimate_confidence?: string | null;
  estimate_basis?: Array<{source: string; platform?: string; detail: string; url?: string | null; price_eur: number}> | null;
  enrichment_version?: string | null;
  best_market?: string | null;
  best_market_reasoning?: string | null;
  buyer_profile?: { who_buys?: string; sell_where?: string; demand_level?: string } | null;
  listing?: { resale_title?: string; resale_description?: string; tags?: string[] } | null;
  inspection_checklist?: string[] | null;
  conviction?: string | null;
  seller_location?: string | null;
  landed_cost_eur?: number | null;
  expected_resale_eur?: number | null;
  predicted_hammer_eur?: number | null;
  max_bid_eur?: number | null;
  hammer_prediction_method?: string | null;
  demand_summary?: string | null;
  demand_detail?: Record<string, any> | null;
  rationale?: string | null;
  risk_flags?: string[];
  user_actions?: string[];
}

export interface ParsedFields {
  parser_version: string;
  title?: string | null;
  subtitle?: string | null;
  description?: string | null;
  category_raw?: string | null;
  condition_text?: string | null;
  dimensions_text?: string | null;
  current_bid?: number | null;
  estimate_low?: number | null;
  estimate_high?: number | null;
  currency?: string | null;
  auction_end_time?: string | null;
  time_left_text?: string | null;
  provenance_text?: string | null;
  seller_location?: string | null;
  auction_house_name?: string | null;
  raw_designer_mentions?: string[] | null;
  raw_material_mentions?: string[] | null;
  parse_confidence: number;
}

export interface EnrichmentOutput {
  agent_name: string;
  agent_version: string;
  output_json: Record<string, any>;
  confidence?: number | null;
  completed_at?: string | null;
}

export interface FetchRecord {
  fetched_at: string;
  fetch_type: string;
  http_status?: number | null;
  success: boolean;
  error_message?: string | null;
}

export interface LotImage {
  url: string;
  local_path?: string | null;
  sort_order: number;
}

export interface LotDetail extends LotCard {
  parsed_fields?: ParsedFields | null;
  normalized_fields?: Record<string, any> | null;
  enrichments?: EnrichmentOutput[];
  fetch_history?: FetchRecord[];
  images?: LotImage[];
  notes?: string | null;
}

export interface ViewResponse {
  view_name: string;
  lots: LotCard[];
  total: number;
  filters?: Record<string, any>;
}

export interface WantedListingCard {
  id: number;
  finn_id: string;
  url: string;
  title: string;
  offered_price?: number | null;
  currency: string;
  brand?: string | null;
  designer?: string | null;
  category?: string | null;
  buyer_location?: string | null;
  image_urls?: string[] | null;
  published_text?: string | null;
  match_reason?: string | null;
}

export interface WantedViewResponse {
  listings: WantedListingCard[];
  total: number;
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
