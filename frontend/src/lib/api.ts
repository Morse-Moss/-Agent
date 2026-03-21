import { getAuthToken } from "./auth";
import type {
  ApiKeys,
  AuthResponse,
  BrandProfile,
  GenerationResult,
  ProjectDetail,
  ProjectListItem,
  ProviderSettings,
  ProviderTestResult,
} from "./types";

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";
const apiBaseUrl = rawBaseUrl.replace(/\/$/, "");
const storageBaseUrl = apiBaseUrl.replace(/\/api$/, "") || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(init?.headers ?? {});

  if (!headers.has("Content-Type") && !(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const maybeJson = await response.json().catch(() => null);
    throw new Error(maybeJson?.detail ?? `请求失败，状态码：${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
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

export function createProject(payload: Record<string, unknown>): Promise<ProjectDetail> {
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

export function generateProject(projectId: number, payload: Record<string, unknown>): Promise<GenerationResult> {
  return request<GenerationResult>(`/projects/${projectId}/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function regenerateVersion(projectId: number, versionId: number, payload: Record<string, unknown>): Promise<GenerationResult> {
  return request<GenerationResult>(`/projects/${projectId}/versions/${versionId}/regenerate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reviewVersion(projectId: number, versionId: number, payload: Record<string, unknown>): Promise<ProjectDetail> {
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

export function deriveVersion(projectId: number, versionId: number, payload: Record<string, unknown>): Promise<GenerationResult> {
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

export function saveBrandProfile(payload: Record<string, unknown>): Promise<BrandProfile> {
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

export function saveApiKeys(payload: Record<string, unknown>): Promise<ApiKeys> {
  return request<ApiKeys>("/settings/api-keys", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProviderSettings(): Promise<ProviderSettings> {
  return request<ProviderSettings>("/settings/providers");
}

export function saveProviderSettings(payload: Record<string, unknown>): Promise<ProviderSettings> {
  return request<ProviderSettings>("/settings/providers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function testImageProvider(): Promise<ProviderTestResult> {
  return request<ProviderTestResult>("/settings/providers/test-image", {
    method: "POST",
  });
}
