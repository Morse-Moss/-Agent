// v0.5 Task / Category / Candidate types

export type EntryType = "competitor_link" | "white_bg_upload" | "image_scene_video";
export type TaskStep = "input" | "product_select" | "scene_generate" | "content_extend" | "review_finalize";
export type TaskStatus = "active" | "error" | "completed" | "cancelled";

export interface ProductCategory {
  id: number;
  name: string;
  parent_id: number | null;
  prompt_template: string;
  scene_keywords: string[];
  is_active: boolean;
  sort_order: number;
  children: ProductCategory[];
}

export interface Candidate {
  id: number;
  task_id: number;
  source_type: string;
  file_path: string;
  is_selected: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface CrawlRun {
  id: number;
  task_id: number;
  source_url: string;
  source_platform: string;
  status: string;
  error_message: string;
  created_at: string;
}

export interface Task {
  id: number;
  project_id: number | null;
  entry_type: EntryType;
  current_step: TaskStep;
  task_config_json: Record<string, unknown>;
  product_category_id: number | null;
  status: TaskStatus;
  created_at: string;
  candidates: Candidate[];
  crawl_runs: CrawlRun[];
}

export const STEP_LABELS: Record<TaskStep, string> = {
  input: "输入需求",
  product_select: "选择产品",
  scene_generate: "产出场景",
  content_extend: "扩展内容",
  review_finalize: "审核定稿",
};

export const ENTRY_LABELS: Record<EntryType, string> = {
  competitor_link: "竞品链接",
  white_bg_upload: "白底图上传",
  image_scene_video: "图片+场景描述",
};

/** Ordered list of steps — index determines progression order. */
export const STEP_ORDER: TaskStep[] = [
  "input",
  "product_select",
  "scene_generate",
  "content_extend",
  "review_finalize",
];

/** Returns true when `current` step comes before `target` in the pipeline. */
export function canAdvanceTo(current: TaskStep, target: TaskStep): boolean {
  return STEP_ORDER.indexOf(current) < STEP_ORDER.indexOf(target);
}
