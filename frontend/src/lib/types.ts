export type ReviewStatus = "unreviewed" | "approved" | "rejected";
export type ProjectStatus = ReviewStatus | "finalized";

export interface UserSummary {
  id: number;
  username: string;
  role: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserSummary;
}

export interface Asset {
  id: number;
  version_id: number;
  file_path: string;
  asset_type: string;
  width: number | null;
  height: number | null;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  project_id: number;
  version_id: number | null;
  sender_type: string;
  content: string;
  created_at: string;
}

export interface Version {
  id: number;
  project_id: number;
  version_no: number;
  prompt_text: string;
  title_text: string;
  review_status: ReviewStatus;
  review_comment: string;
  is_final: boolean;
  parent_version_id: number | null;
  input_snapshot_json: Record<string, unknown>;
  created_at: string;
  assets: Asset[];
}

export interface ProjectListItem {
  id: number;
  name: string;
  page_type: string;
  platform: string;
  product_name: string;
  status: ProjectStatus;
  latest_version_id: number | null;
  final_version_id: number | null;
  cover_asset_path: string | null;
  cover_asset_type: string | null;
  cover_width: number | null;
  cover_height: number | null;
  latest_version_no: number | null;
  created_at: string;
}

export interface ProjectDetail extends ProjectListItem {
  brand_profile_id: number | null;
  versions: Version[];
  chat_messages: ChatMessage[];
}

export interface BrandProfile {
  id: number;
  name: string;
  description: string;
  style_summary: string;
  recommended_keywords: string[];
}

export interface ApiKeys {
  llm_api_key: string | null;
  image_api_key: string | null;
  cutout_api_key: string | null;
  llm_api_key_source: "env" | "db" | "unset";
  image_api_key_source: "env" | "db" | "unset";
  cutout_api_key_source: "env" | "db" | "unset";
}

export interface ProviderSettings {
  llm_provider: string;
  llm_api_url: string | null;
  llm_model: string | null;
  llm_timeout_seconds: number;
  llm_api_key_header: string;
  image_provider: string;
  image_api_url: string | null;
  image_model: string | null;
  image_timeout_seconds: number;
  image_api_key_header: string;
  cutout_provider: string;
  llm_provider_source: "env" | "db" | "default" | "unset";
  llm_api_url_source: "env" | "db" | "default" | "unset";
  llm_model_source: "env" | "db" | "default" | "unset";
  llm_timeout_seconds_source: "env" | "db" | "default" | "unset";
  llm_api_key_header_source: "env" | "db" | "default" | "unset";
  image_provider_source: "env" | "db" | "default" | "unset";
  image_api_url_source: "env" | "db" | "default" | "unset";
  image_model_source: "env" | "db" | "default" | "unset";
  image_timeout_seconds_source: "env" | "db" | "default" | "unset";
  image_api_key_header_source: "env" | "db" | "default" | "unset";
  cutout_provider_source: "env" | "db" | "default" | "unset";
}

export interface ProviderPreset {
  preset_name: string;
  scope: "llm" | "image";
  provider: string;
  api_url: string | null;
  model: string | null;
  timeout_seconds: number;
  api_key_header: string;
  has_api_key: boolean;
}

export interface ProviderPresets {
  llm_presets: ProviderPreset[];
  image_presets: ProviderPreset[];
}

export interface ProviderTestResult {
  ok: boolean;
  provider: string;
  detail: string;
  file_path: string | null;
}

export interface GenerationResult {
  mode: "clarify" | "chat" | "generated";
  project: ProjectDetail;
  assistant_message: ChatMessage;
  version: Version | null;
  questions: string[];
}
