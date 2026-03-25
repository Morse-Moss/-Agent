import { getAuthToken } from "./auth";
import type {
  ApiKeys,
  AuthResponse,
  BrandProfile,
  GenerationResult,
  ProjectDetail,
  ProjectListItem,
  ProviderPresets,
  ProviderSettings,
  ProviderTestResult,
} from "./types";
import type { Candidate, ProductCategory, Task } from "./task-types";

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";
const apiBaseUrl = rawBaseUrl.replace(/\/$/, "");
const storageBaseUrl = apiBaseUrl.replace(/\/api$/, "") || "";

const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * Returns true when the error is a network / connectivity issue
 * (as opposed to a business-logic error returned by the server).
 */
export function isNetworkError(err: unknown): boolean {
  if (err instanceof TypeError && /fetch|network/i.test(err.message)) return true;
  if (err instanceof DOMException && err.name === "AbortError") return true;
  if (err instanceof Error && /超时/.test(err.message)) return true;
  return false;
}

/** Query-key constants used by mutation helpers for auto-invalidation. */
export const QK = {
  task: (id: number) => ["task", id] as const,
  categories: ["categories"] as const,
} as const;

async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(init?.headers ?? {});

  if (!headers.has("Content-Type") && !(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const controller = new AbortController();
  const timeoutMs = init?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const maybeJson = await response.json().catch(() => null);
      throw new Error(maybeJson?.detail ?? `请求失败，状态码：${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`请求超时（${timeoutMs / 1000}秒）`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function getAssetUrl(filePath: string): string {
  return `${storageBaseUrl}/storage/${filePath}`;
}

export function login(username: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function listProjects(status?: string): Promise<ProjectListItem[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<ProjectListItem[]>(`/projects${query}`);
}

export function createProject(payload: {
  name?: string;
  page_type?: string;
  platform?: string;
  product_name?: string;
  brand_profile_id?: number;
}): Promise<ProjectDetail> {
  return request<ProjectDetail>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteProject(projectId: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/projects/${projectId}`, {
    method: "DELETE",
  });
}

export function getProject(projectId: number): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/projects/${projectId}`);
}

export function generateProject(projectId: number, payload: {
  message: string;
  source_image_path?: string | null;
  brand_profile_id?: number;
  guide_fields?: Record<string, unknown>;
}): Promise<GenerationResult> {
  return request<GenerationResult>(`/projects/${projectId}/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function regenerateVersion(projectId: number, versionId: number, payload: {
  message: string;
  source_image_path?: string | null;
  brand_profile_id?: number;
  guide_fields?: Record<string, unknown>;
}): Promise<GenerationResult> {
  return request<GenerationResult>(`/projects/${projectId}/versions/${versionId}/regenerate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reviewVersion(projectId: number, versionId: number, payload: {
  action: "approved" | "rejected";
  comment?: string;
}): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/projects/${projectId}/versions/${versionId}/review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function finalizeVersion(projectId: number, versionId: number): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/projects/${projectId}/versions/${versionId}/finalize`, {
    method: "POST",
  });
}

export function deriveVersion(projectId: number, versionId: number, payload: {
  message: string;
}): Promise<GenerationResult> {
  return request<GenerationResult>(`/projects/${projectId}/versions/${versionId}/derive`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadImage(file: File): Promise<{ file_path: string; width: number | null; height: number | null }> {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append("image", file);

  const response = await fetch(`${apiBaseUrl}/upload/image`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });

  if (!response.ok) {
    const maybeJson = await response.json().catch(() => null);
    throw new Error(maybeJson?.detail ?? "图片上传失败");
  }

  return (await response.json()) as { file_path: string; width: number | null; height: number | null };
}

export function getBrandProfile(): Promise<BrandProfile> {
  return request<BrandProfile>("/brand/profile");
}

export function saveBrandProfile(payload: {
  name?: string;
  description?: string;
  style_summary?: string;
  recommended_keywords?: string[];
}): Promise<BrandProfile> {
  return request<BrandProfile>("/brand/profile", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function summarizeBrand(payload: { description: string }): Promise<{ style_summary: string; recommended_keywords: string[] }> {
  return request<{ style_summary: string; recommended_keywords: string[] }>("/brand/profile/summarize", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getApiKeys(): Promise<ApiKeys> {
  return request<ApiKeys>("/settings/api-keys");
}

export function saveApiKeys(payload: {
  llm_api_key?: string | null;
  image_api_key?: string | null;
  cutout_api_key?: string | null;
}): Promise<ApiKeys> {
  return request<ApiKeys>("/settings/api-keys", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProviderSettings(): Promise<ProviderSettings> {
  return request<ProviderSettings>("/settings/providers");
}

export function saveProviderSettings(payload: Partial<ProviderSettings>): Promise<ProviderSettings> {
  return request<ProviderSettings>("/settings/providers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProviderPresets(): Promise<ProviderPresets> {
  return request<ProviderPresets>("/settings/provider-presets");
}

export function saveProviderPreset(payload: {
  scope: "llm" | "image";
  preset_name: string;
  provider: string;
  api_url?: string | null;
  model?: string | null;
  timeout_seconds?: number;
  api_key_header?: string;
  api_key?: string | null;
  include_api_key?: boolean;
}): Promise<ProviderPresets> {
  return request<ProviderPresets>("/settings/provider-presets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function applyProviderPreset(payload: {
  scope: "llm" | "image";
  preset_name: string;
}): Promise<ProviderSettings> {
  return request<ProviderSettings>("/settings/provider-presets/apply", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteProviderPreset(payload: {
  scope: "llm" | "image";
  preset_name: string;
}): Promise<ProviderPresets> {
  return request<ProviderPresets>("/settings/provider-presets/delete", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function testLLMProvider(): Promise<ProviderTestResult> {
  return request<ProviderTestResult>("/settings/providers/test-llm", {
    method: "POST",
  });
}

export function testImageProvider(): Promise<ProviderTestResult> {
  return request<ProviderTestResult>("/settings/providers/test-image", {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// v0.5 Task / Category / Candidate APIs
// ---------------------------------------------------------------------------

export function createTask(payload: {
  entry_type: string;
  source_url?: string;
  product_category_id?: number;
  task_config_json?: Record<string, unknown>;
}): Promise<Task> {
  return request<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) });
}

export function getTask(taskId: number): Promise<Task> {
  return request<Task>(`/tasks/${taskId}`);
}

export function advanceTask(
  taskId: number,
  targetStep?: string,
  expectedStep?: string,
): Promise<Task> {
  return request<Task>(`/tasks/${taskId}/advance`, {
    method: "POST",
    body: JSON.stringify({
      target_step: targetStep ?? null,
      expected_step: expectedStep ?? null,
    }),
  });
}

export function selectCandidate(taskId: number, candidateId: number): Promise<Task> {
  return request<Task>(`/tasks/${taskId}/select-candidate`, {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export function listCandidates(taskId: number): Promise<Candidate[]> {
  return request<Candidate[]>(`/tasks/${taskId}/candidates`);
}

export function listCategories(): Promise<ProductCategory[]> {
  return request<ProductCategory[]>("/categories");
}

export function createCategory(payload: {
  name: string;
  parent_id?: number;
  prompt_template?: string;
  scene_keywords?: string[];
}): Promise<ProductCategory> {
  return request<ProductCategory>("/categories", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------------
// v0.5 Video / Copy / Crawl APIs
// ---------------------------------------------------------------------------

export function startCrawl(taskId: number): Promise<unknown> {
  return request(`/tasks/${taskId}/crawl`, { method: "POST" });
}

export function getCrawlStatus(taskId: number): Promise<unknown[]> {
  return request(`/tasks/${taskId}/crawl-status`);
}

export function generateVideo(taskId: number, payload: {
  prompt: string;
  image_url?: string;
  duration_seconds?: number;
  orientation?: string;
  resolution?: string;
}): Promise<{ success: boolean; video_url?: string; error?: string }> {
  return request(`/tasks/${taskId}/generate-video`, {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: 120_000,
  });
}

export function generateCopy(taskId: number, payload: {
  product_name: string;
  scene_description?: string;
  selling_points?: string[];
  platforms?: string[];
}): Promise<{ copies: Record<string, string> }> {
  return request(`/tasks/${taskId}/generate-copy`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
