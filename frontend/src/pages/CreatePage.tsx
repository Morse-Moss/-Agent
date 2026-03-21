import { useEffect, useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Form, Input, Select, Space, Tag, Typography, Upload, message } from "antd";
import type { UploadProps } from "antd";
import { Link, useSearchParams } from "react-router-dom";

import { AssetPreview } from "../components/AssetPreview";
import { StatusTag } from "../components/StatusTag";
import { createProject, generateProject, getAssetUrl, getBrandProfile, getProject, regenerateVersion, uploadImage } from "../lib/api";
import type { Asset, ProjectDetail, Version } from "../lib/types";

const pageOptions = [
  { label: "淘宝主图", value: "main_image" },
  { label: "详情页模块", value: "detail_module" },
  { label: "品牌 Banner", value: "banner" },
];

function parsePositiveInt(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function buildGuideFields(values: Record<string, unknown>) {
  return {
    page_type: values.page_type,
    platform: values.platform,
    product_name: values.product_name,
    style_keywords: String(values.style_keywords ?? "")
      .split(/[,\n]/)
      .map((item: string) => item.trim())
      .filter(Boolean),
    selling_points: String(values.selling_points ?? "")
      .split(/[,\n]/)
      .map((item: string) => item.trim())
      .filter(Boolean),
  };
}

function getSourceImagePath(version: Version | null): string | null {
  if (!version) {
    return null;
  }
  const value = version.input_snapshot_json["source_image_path"];
  return typeof value === "string" && value.trim() ? value : null;
}

function getPreviewAsset(version: Version | null): Asset | null {
  if (!version?.assets.length) {
    return null;
  }
  return version.assets.find((asset) => asset.asset_type === "final_export") ?? version.assets[version.assets.length - 1];
}

export function CreatePage(): JSX.Element {
  const [form] = Form.useForm();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const linkedProjectId = parsePositiveInt(searchParams.get("projectId"));
  const linkedVersionId = parsePositiveInt(searchParams.get("versionId"));

  const brandQuery = useQuery({
    queryKey: ["brand-profile"],
    queryFn: getBrandProfile,
  });
  const linkedProjectQuery = useQuery({
    queryKey: ["project", linkedProjectId],
    queryFn: () => getProject(linkedProjectId as number),
    enabled: linkedProjectId !== null,
  });

  const [chatInput, setChatInput] = useState("");
  const [currentProject, setCurrentProject] = useState<ProjectDetail | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [sourceImagePath, setSourceImagePath] = useState<string | null>(null);
  const [uploadLabel, setUploadLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!linkedProjectQuery.data) {
      return;
    }

    const project = linkedProjectQuery.data;
    const versionId = linkedVersionId ?? project.latest_version_id ?? project.versions.at(-1)?.id ?? null;
    const version = project.versions.find((item) => item.id === versionId) ?? project.versions.at(-1) ?? null;
    const inheritedSourceImagePath = getSourceImagePath(version);
    const styleKeywords = version ? version.input_snapshot_json["style_keywords"] : undefined;
    const sellingPoints = version ? version.input_snapshot_json["selling_points"] : undefined;

    setCurrentProject(project);
    setSelectedVersionId(version?.id ?? null);
    setSourceImagePath(inheritedSourceImagePath);
    setUploadLabel(inheritedSourceImagePath ? `沿用版本源图：${inheritedSourceImagePath}` : "");
    form.setFieldsValue({
      name: project.name,
      page_type: project.page_type,
      platform: project.platform,
      product_name: project.product_name,
      style_keywords: Array.isArray(styleKeywords) ? (styleKeywords as string[]).join(", ") : "",
      selling_points: Array.isArray(sellingPoints) ? (sellingPoints as string[]).join(", ") : "",
    });
  }, [form, linkedProjectQuery.data, linkedVersionId]);

  const versions = currentProject?.versions ?? [];
  const latestVersion = versions.at(-1) ?? null;
  const activeVersion = (selectedVersionId ? versions.find((item) => item.id === selectedVersionId) : null) ?? latestVersion ?? null;
  const versionList = versions.slice().reverse();

  function syncSearchParams(projectId: number | null, versionId: number | null): void {
    const nextParams = new URLSearchParams();
    if (projectId) {
      nextParams.set("projectId", String(projectId));
    }
    if (versionId) {
      nextParams.set("versionId", String(versionId));
    }
    setSearchParams(nextParams);
  }

  function resetWorkspace(): void {
    setCurrentProject(null);
    setSelectedVersionId(null);
    setChatInput("");
    setSourceImagePath(null);
    setUploadLabel("");
    form.resetFields();
    form.setFieldsValue({
      page_type: "main_image",
      platform: "taobao",
    });
    syncSearchParams(null, null);
  }

  function selectVersionAsBase(version: Version): void {
    setSelectedVersionId(version.id);
    syncSearchParams(currentProject?.id ?? null, version.id);
    const inheritedSourceImagePath = getSourceImagePath(version);
    setSourceImagePath(inheritedSourceImagePath);
    setUploadLabel(inheritedSourceImagePath ? `沿用版本源图：${inheritedSourceImagePath}` : "");
  }

  async function ensureProject(): Promise<ProjectDetail> {
    if (currentProject) {
      return currentProject;
    }

    const values = form.getFieldsValue();
    const project = await createProject({
      name: values.name,
      page_type: values.page_type,
      platform: values.platform,
      product_name: values.product_name,
      brand_profile_id: brandQuery.data?.id,
    });
    setCurrentProject(project);
    syncSearchParams(project.id, null);
    return project;
  }

  const uploadProps: UploadProps = {
    maxCount: 1,
    customRequest: async ({ file, onSuccess, onError }) => {
      try {
        const result = await uploadImage(file as File);
        setSourceImagePath(result.file_path);
        setUploadLabel(`当前源图：${result.file_path}，${result.width ?? "-"} x ${result.height ?? "-"}`);
        onSuccess?.(result);
        message.success("源图上传成功");
      } catch (error) {
        const err = error instanceof Error ? error : new Error("上传失败");
        onError?.(err);
        message.error(err.message);
      }
    },
  };

  return (
    <div className="page-grid">
      <Card className="page-hero-card">
        <Space direction="vertical" size={6}>
          <Typography.Text className="page-kicker">Creative Workbench</Typography.Text>
          <Typography.Title level={3} style={{ margin: 0 }}>
            对话式创作工作台
          </Typography.Title>
          <Typography.Text type="secondary">
            在同一工作台里完成参数补充、聊天创作、版本切换和图片预览。工作台专注创作，审核与定稿仍保留在作品详情页。
          </Typography.Text>
        </Space>
      </Card>

      <div className="create-grid">
        <Card
          className="workbench-sidebar"
          title="创作参数"
          extra={<Button onClick={resetWorkspace}>新建会话</Button>}
        >
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              page_type: "main_image",
              platform: "taobao",
            }}
          >
            <Form.Item label="作品名称" name="name">
              <Input placeholder="可留空，系统会根据产品名自动命名" />
            </Form.Item>
            <Form.Item label="产品名称" name="product_name">
              <Input placeholder="例如：广告材料铝材 / 铝单板 / 铝型材" />
            </Form.Item>
            <Form.Item label="页面类型" name="page_type">
              <Select options={pageOptions} />
            </Form.Item>
            <Form.Item label="平台" name="platform">
              <Select options={[{ label: "淘宝", value: "taobao" }]} />
            </Form.Item>
            <Form.Item label="风格关键词" name="style_keywords">
              <Input placeholder="例如：工业简洁，金属质感，高级感" />
            </Form.Item>
            <Form.Item label="卖点关键词" name="selling_points">
              <Input placeholder="例如：耐腐蚀，高强度，支持定制" />
            </Form.Item>
            <Form.Item label="白底图上传">
              <Upload {...uploadProps}>
                <Button block>上传白底图</Button>
              </Upload>
              <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                {uploadLabel || "建议上传白底产品图，系统会优先按抠图合成的方式生成更稳定的主图。"}
              </Typography.Paragraph>
            </Form.Item>
          </Form>
        </Card>

        <Card className="chat-panel">
          <div className="workbench-summary">
            <div>
              <Typography.Title level={4}>创作聊天</Typography.Title>
              <Typography.Paragraph type="secondary">
                直接输入自然语言需求即可。如果当前选中了某个版本，新一轮生成会基于该版本继续演化。
              </Typography.Paragraph>
            </div>
            <Space wrap>
              {currentProject ? (
                <>
                  <Tag color="cyan">项目：{currentProject.name}</Tag>
                  {activeVersion ? <Tag color="geekblue">当前基础版本 V{activeVersion.version_no}</Tag> : null}
                  <Link to={`/projects/${currentProject.id}`}>打开完整版本记录</Link>
                </>
              ) : (
                <Typography.Text type="secondary">首次生成时会自动创建项目。</Typography.Text>
              )}
            </Space>
          </div>

          <div className="chat-list workbench-chat-list">
            {currentProject?.chat_messages.length ? (
              currentProject.chat_messages.map((item) => (
                <div
                  key={item.id}
                  className={`chat-bubble ${item.sender_type === "user" ? "chat-bubble-user" : "chat-bubble-assistant"}`}
                >
                  <Typography.Paragraph style={{ marginBottom: 0, color: "inherit", whiteSpace: "pre-wrap" }}>
                    {item.content}
                  </Typography.Paragraph>
                </div>
              ))
            ) : (
              <Card size="small" className="chat-empty-card">
                <Typography.Text type="secondary">
                  示例：请做一版淘宝主图，突出耐腐蚀和支持定制，整体偏工业简洁，画面要像成熟的广告材料电商图。
                </Typography.Text>
              </Card>
            )}
          </div>

          <div className="chat-composer">
            <Input.TextArea
              rows={8}
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              className="chat-input"
              style={{ resize: "both", minHeight: 180 }}
              placeholder={
                activeVersion
                  ? `基于 V${activeVersion.version_no} 输入新的修改意见，例如：背景更高级，主体更靠右，减少杂物感。`
                  : "输入主图需求，系统会先理解聊天内容，再生成可继续迭代的版本。"
              }
            />
            <Space wrap>
              <Button
                type="primary"
                loading={submitting}
                onClick={async () => {
                  if (!chatInput.trim()) {
                    message.warning("先输入一条创作指令再生成。");
                    return;
                  }
                  setSubmitting(true);
                  try {
                    const values = form.getFieldsValue();
                    const guideFields = buildGuideFields(values);
                    const project = await ensureProject();
                    const result =
                      activeVersion && project.id === currentProject?.id
                        ? await regenerateVersion(project.id, activeVersion.id, {
                            message: chatInput,
                            source_image_path: sourceImagePath,
                            brand_profile_id: brandQuery.data?.id,
                            guide_fields: guideFields,
                          })
                        : await generateProject(project.id, {
                            message: chatInput,
                            source_image_path: sourceImagePath,
                            brand_profile_id: brandQuery.data?.id,
                            guide_fields: guideFields,
                          });

                    setCurrentProject(result.project);
                    const nextVersionId = result.version?.id ?? result.project.latest_version_id ?? null;
                    setSelectedVersionId(nextVersionId);
                    syncSearchParams(result.project.id, nextVersionId);
                    setChatInput("");
                    await queryClient.invalidateQueries({ queryKey: ["projects"] });
                    await queryClient.invalidateQueries({ queryKey: ["project", project.id] });
                    message.success(result.mode === "clarify" ? "系统已追问关键信息。" : "新的主图版本已生成。");
                  } catch (error) {
                    message.error(error instanceof Error ? error.message : "生成失败");
                  } finally {
                    setSubmitting(false);
                  }
                }}
              >
                {activeVersion ? "基于当前版本继续生成" : "开始生成"}
              </Button>
              {activeVersion && latestVersion && activeVersion.id !== latestVersion.id ? (
                <Button
                  onClick={() => {
                    setSelectedVersionId(latestVersion.id);
                    syncSearchParams(currentProject?.id ?? null, latestVersion.id);
                    const inheritedSourceImagePath = getSourceImagePath(latestVersion);
                    setSourceImagePath(inheritedSourceImagePath);
                    setUploadLabel(inheritedSourceImagePath ? `沿用版本源图：${inheritedSourceImagePath}` : "");
                  }}
                >
                  切回最新版本继续修改
                </Button>
              ) : null}
            </Space>
          </div>
        </Card>

        <Card className="preview-panel" title="实时预览">
          {activeVersion ? (
            <Space direction="vertical" size="middle" style={{ width: "100%" }}>
              <div className="preview-meta">
                <Space wrap>
                  <Tag color="geekblue">V{activeVersion.version_no}</Tag>
                  <StatusTag status={activeVersion.is_final ? "finalized" : activeVersion.review_status} />
                </Space>
                <Typography.Text type="secondary">
                  {activeVersion.prompt_text || "当前版本暂无创作指令"}
                </Typography.Text>
              </div>
              <AssetPreview assets={activeVersion.assets} />
            </Space>
          ) : (
            <Typography.Text type="secondary">生成完成后，图片会直接显示在这里。</Typography.Text>
          )}

          <div className="version-stack">
            <div className="version-stack-header">
              <Typography.Title level={5} style={{ margin: 0 }}>
                版本工作区
              </Typography.Title>
              {currentProject ? <Link to={`/projects/${currentProject.id}`}>查看作品详情</Link> : null}
            </div>

            {versionList.length ? (
              versionList.map((version) => {
                const previewAsset = getPreviewAsset(version);

                return (
                  <div
                    key={version.id}
                    className={`version-item ${activeVersion?.id === version.id ? "version-item-active" : ""}`}
                  >
                    <div className="version-item-layout">
                      <div className="version-thumb">
                        {previewAsset ? (
                          <img src={getAssetUrl(previewAsset.file_path)} alt={`版本 ${version.version_no}`} />
                        ) : (
                          <div className="version-thumb-placeholder">
                            <span>无图</span>
                          </div>
                        )}
                      </div>
                      <div className="version-item-copy">
                        <Space wrap>
                          <Typography.Text strong>版本 V{version.version_no}</Typography.Text>
                          <StatusTag status={version.is_final ? "finalized" : version.review_status} />
                        </Space>
                        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                          {version.prompt_text || "暂无创作指令"}
                        </Typography.Paragraph>
                        <Button
                          size="small"
                          type={activeVersion?.id === version.id ? "primary" : "default"}
                          onClick={() => selectVersionAsBase(version)}
                        >
                          {activeVersion?.id === version.id ? "当前基础版本" : "设为基础版本"}
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <Typography.Text type="secondary">
                生成第一版之后，这里会显示所有版本，并支持直接切回任意版本继续修改。
              </Typography.Text>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
