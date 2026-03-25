import type { Version } from "./types";

export function getVersionRunInfo(version: Version | null): { llm: string; image: string } {
  if (!version) {
    return { llm: "未记录", image: "未记录" };
  }
  const llmProvider = String(version.input_snapshot_json["llm_provider_used"] ?? "").trim();
  const llmModel = String(version.input_snapshot_json["llm_model_used"] ?? "").trim();
  const imageProvider = String(version.input_snapshot_json["image_provider_used"] ?? "").trim();
  const imageModel = String(version.input_snapshot_json["image_model_used"] ?? "").trim();

  return {
    llm: llmProvider ? `${llmProvider}${llmModel ? ` / ${llmModel}` : ""}` : "未记录",
    image: imageProvider ? `${imageProvider}${imageModel ? ` / ${imageModel}` : ""}` : "未记录",
  };
}
