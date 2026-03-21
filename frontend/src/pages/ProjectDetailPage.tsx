import { useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Empty, Input, Modal, Space, Typography, message } from "antd";
import { useNavigate, useParams } from "react-router-dom";

import { AssetPreview } from "../components/AssetPreview";
import { StatusTag } from "../components/StatusTag";
import { deriveVersion, finalizeVersion, getProject, reviewVersion } from "../lib/api";
import type { Version } from "../lib/types";

type ActionDialogMode = "approve" | "reject" | "derive" | null;

const dialogTitleMap: Record<Exclude<ActionDialogMode, null>, string> = {
  approve: "通过审核",
  reject: "驳回版本",
  derive: "派生新版本",
};

const dialogHintMap: Record<Exclude<ActionDialogMode, null>, string> = {
  approve: "可选填写审核备注，留空则直接通过。",
  reject: "请输入驳回意见，这段内容会自动写回聊天区，作为下一轮修改的上下文。",
  derive: "请输入基于当前定稿版本继续延展的新方向。",
};

export function ProjectDetailPage(): JSX.Element {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const numericProjectId = Number(projectId);
  const queryClient = useQueryClient();
  const [dialogMode, setDialogMode] = useState<ActionDialogMode>(null);
  const [dialogVersion, setDialogVersion] = useState<Version | null>(null);
  const [dialogValue, setDialogValue] = useState("");
  const [dialogSubmitting, setDialogSubmitting] = useState(false);

  const projectQuery = useQuery({
    queryKey: ["project", numericProjectId],
    queryFn: () => getProject(numericProjectId),
    enabled: Number.isFinite(numericProjectId),
  });

  async function refreshProject(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: ["project", numericProjectId] });
    await queryClient.invalidateQueries({ queryKey: ["projects"] });
  }

  function openActionDialog(mode: Exclude<ActionDialogMode, null>, version: Version): void {
    setDialogMode(mode);
    setDialogVersion(version);
    if (mode === "reject") {
      setDialogValue("请进一步突出定制能力，并减少无关装饰元素。");
      return;
    }
    if (mode === "derive") {
      setDialogValue("在保留主结构的基础上，做一版更偏品牌展示的版本。");
      return;
    }
    setDialogValue("");
  }

  function closeActionDialog(): void {
    if (dialogSubmitting) {
      return;
    }
    setDialogMode(null);
    setDialogVersion(null);
    setDialogValue("");
  }

  if (!projectId || Number.isNaN(numericProjectId)) {
    return (
      <Card className="surface-card">
        <Typography.Text>项目编号无效。</Typography.Text>
      </Card>
    );
  }

  const project = projectQuery.data;

  return (
    <div className="page-grid">
      <Card className="page-hero-card">
        <Space direction="vertical" size={6}>
          <Typography.Text className="page-kicker">Project Detail</Typography.Text>
          <Typography.Title level={3} style={{ margin: 0 }}>
            作品详情
          </Typography.Title>
          {project ? (
            <Space wrap>
              <Typography.Text strong>{project.name}</Typography.Text>
              <StatusTag status={project.status} />
              <Typography.Text type="secondary">产品：{project.product_name || "待补充"}</Typography.Text>
              <Typography.Text type="secondary">版本数：{project.versions.length}</Typography.Text>
            </Space>
          ) : (
            <Typography.Text type="secondary">查看作品的版本历史、审核意见和资产预览。</Typography.Text>
          )}
        </Space>
      </Card>

      {project ? (
        <div className="detail-grid">
          <Card className="surface-card" title="聊天与审核上下文">
            <div className="chat-list">
              {project.chat_messages.length ? (
                project.chat_messages.map((item) => (
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
                <Empty description="当前项目还没有聊天记录。" />
              )}
            </div>
          </Card>

          <div className="detail-version-stack">
            {project.versions
              .slice()
              .reverse()
              .map((version) => (
                <Card
                  key={version.id}
                  className="surface-card"
                  title={
                    <Space wrap>
                      <Typography.Text strong>版本 V{version.version_no}</Typography.Text>
                      <StatusTag status={version.is_final ? "finalized" : version.review_status} />
                    </Space>
                  }
                  extra={version.id === project.latest_version_id ? <Typography.Text type="secondary">当前最新</Typography.Text> : null}
                >
                  <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                    <div className="project-meta-list">
                      <div className="project-meta-item">
                        <span className="project-meta-label">标题</span>
                        <span>{version.title_text || "未生成标题"}</span>
                      </div>
                      <div className="project-meta-item">
                        <span className="project-meta-label">创作指令</span>
                        <span>{version.prompt_text || "暂无创作指令"}</span>
                      </div>
                      <div className="project-meta-item">
                        <span className="project-meta-label">父版本</span>
                        <span>{version.parent_version_id ? `版本 ID ${version.parent_version_id}` : "首版"}</span>
                      </div>
                      <div className="project-meta-item">
                        <span className="project-meta-label">创建时间</span>
                        <span>{new Date(version.created_at).toLocaleString("zh-CN")}</span>
                      </div>
                    </div>
                    {version.review_comment ? (
                      <Typography.Text type="secondary">审核意见：{version.review_comment}</Typography.Text>
                    ) : null}
                    <AssetPreview assets={version.assets} />
                    <Space wrap>
                      <Button
                        type={version.id === project.latest_version_id ? "primary" : "default"}
                        onClick={() => navigate(`/create?projectId=${project.id}&versionId=${version.id}`)}
                      >
                        回到工作台继续修改
                      </Button>
                      <Button onClick={() => openActionDialog("approve", version)}>通过审核</Button>
                      <Button danger onClick={() => openActionDialog("reject", version)}>
                        驳回
                      </Button>
                      <Button
                        type="primary"
                        disabled={version.review_status !== "approved"}
                        onClick={async () => {
                          try {
                            await finalizeVersion(project.id, version.id);
                            await refreshProject();
                            message.success("版本已定稿。");
                          } catch (error) {
                            message.error(error instanceof Error ? error.message : "定稿失败");
                          }
                        }}
                      >
                        定稿归档
                      </Button>
                      <Button disabled={!version.is_final} onClick={() => openActionDialog("derive", version)}>
                        派生新版本
                      </Button>
                    </Space>
                  </Space>
                </Card>
              ))}

            <Button
              onClick={() =>
                navigate(`/create?projectId=${project.id}${project.latest_version_id ? `&versionId=${project.latest_version_id}` : ""}`)
              }
            >
              回到创作工作台
            </Button>
          </div>
        </div>
      ) : (
        <Card className="surface-card">
          {projectQuery.isLoading ? (
            <Typography.Text>正在加载项目详情...</Typography.Text>
          ) : (
            <Empty description="没有找到该项目。" />
          )}
        </Card>
      )}

      <Modal
        open={dialogMode !== null && dialogVersion !== null}
        title={dialogMode ? dialogTitleMap[dialogMode] : ""}
        okText={dialogMode === "derive" ? "创建派生版本" : dialogMode === "reject" ? "确认驳回" : "确认通过"}
        cancelText="取消"
        confirmLoading={dialogSubmitting}
        onCancel={closeActionDialog}
        onOk={async () => {
          if (!project || !dialogMode || !dialogVersion) {
            return;
          }

          if ((dialogMode === "reject" || dialogMode === "derive") && !dialogValue.trim()) {
            message.warning(dialogMode === "reject" ? "请先输入驳回意见。" : "请先输入派生方向。");
            return;
          }

          setDialogSubmitting(true);
          try {
            if (dialogMode === "approve") {
              await reviewVersion(project.id, dialogVersion.id, {
                action: "approved",
                comment: dialogValue.trim(),
              });
              message.success("版本已通过审核。");
            } else if (dialogMode === "reject") {
              await reviewVersion(project.id, dialogVersion.id, {
                action: "rejected",
                comment: dialogValue.trim(),
              });
              message.success("驳回意见已写回聊天区。");
            } else {
              await deriveVersion(project.id, dialogVersion.id, {
                message: dialogValue.trim(),
              });
              message.success("已基于定稿版本派生出新版本。");
            }
            closeActionDialog();
            await refreshProject();
          } catch (error) {
            message.error(
              error instanceof Error
                ? error.message
                : dialogMode === "derive"
                  ? "派生失败"
                  : dialogMode === "reject"
                    ? "驳回失败"
                    : "审核失败",
            );
          } finally {
            setDialogSubmitting(false);
          }
        }}
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Text type="secondary">{dialogMode ? dialogHintMap[dialogMode] : ""}</Typography.Text>
          <Input.TextArea
            rows={5}
            value={dialogValue}
            onChange={(event) => setDialogValue(event.target.value)}
            placeholder={dialogMode ? dialogHintMap[dialogMode] : ""}
          />
        </Space>
      </Modal>
    </div>
  );
}
