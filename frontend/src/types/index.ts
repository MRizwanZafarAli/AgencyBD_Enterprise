export type TabType = 
  | 'overview' 
  | 'doctor'
  | 'radar'
  | 'hunt'
  | 'portfolio'
  | 'sequences'
  | 'governance'
  | 'sourcing' 
  | 'waterfall' 
  | 'deliverability' 
  | 'copycoach' 
  | 'callintel' 
  | 'multimodal' 
  | 'dns' 
  | 'suppression' 
  | 'rbac'
  | 'apidocs';


export interface GoogleMapsLead {
  id?: number | string;
  company_name: string;
  domain: string;
  phone: string;
  rating: number;
  reviews_count: number;
  address: string;
}

export interface LinkedInProfile {
  first_name: string;
  last_name: string;
  title: string;
  headline: string;
  location: string;
  linkedin_url: string;
}

export interface WaterfallCandidate {
  email: string;
  is_primary: boolean;
  gravatar_active: boolean;
  syntax_valid: boolean;
}

export interface WaterfallResearchDossier {
  company_name: string;
  domain: string;
  detected_stack: string[];
  tech_debt_score: number;
  custom_pitch_angle: string;
  hiring_signal: string;
  decision_maker_context: string;
}

export interface WaterfallResult {
  prospect_name: string;
  resolved_email: string;
  confidence_score: number;
  esp_provider: string;
  mx_records: string[];
  catch_all: boolean;
  verification_status: string;
  steps_completed: string[];
  catch_all_decoded?: boolean;
  decoder_evidence?: string;
  candidate_matrix?: WaterfallCandidate[];
  autonomous_research_dossier?: WaterfallResearchDossier;
  estimated_commercial_dollars_saved?: number;
  verdict?: string;
  company?: string;
  domain?: string;
  waterfall_steps_executed?: string[];
}

export interface CopyScoreResult {
  overall_score: number;
  reading_grade: string;
  word_count: number;
  spam_triggers: string[];
  suggestions: string[];
  optimized_version?: string;
}

export interface CallIntelResult {
  talk_ratio: { rep_pct: number; prospect_pct: number };
  questions_asked: number;
  competitors_mentioned: string[];
  pain_points: string[];
  action_items: string[];
  sow_draft: {
    client_name: string;
    scope_of_work: string;
    timeline_weeks: number;
    estimated_investment: string;
  };
}

export interface VideoPitchStoryboard {
  prospect_name: string;
  company_name: string;
  domain: string;
  lcp_score: number;
  scenes: Array<{
    scene_number: number;
    title: string;
    visual_action: string;
    script_audio: string;
  }>;
}
