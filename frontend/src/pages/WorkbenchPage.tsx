import { Button, Card, Input, message, Result, Space, Upload } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useCallback } from "react";

import { StepBar } from "../components/workbench/StepBar";
import { EntryTabs } from "../components/workbench/EntryTabs";
import { CandidateGrid } from "../components/workbench/CandidateGrid";
import { CategorySelector } from "../components/workbench/CategorySelector";
import { ChatPanel } from "../components/workbench/ChatPanel";
import { ResultPanel } from "../components/workbench/ResultPanel";
import {
  createTask,
  getTask,
  advanceTask,
  selectCandidate,
  listCategories,
  uploadImage,
  getBrandProfile,
  isNetworkError,
  QK,
} from "../lib/api";
import type { EntryType, TaskStep } from "../lib/task-types";
import type { ChatMessage } from "../lib/types";

export function WorkbenchPage(): JSX.Element {
  const queryClient = useQueryClient();
  const [activeEntry, setActiveEntry] = useState<EntryType>("white_bg_upload");
  const [taskId, setTaskId] = useState<number | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | undefined>();
  const [sourceImagePath, setSourceImagePath] = useState<string | null>(null);
  const [competitorUrl, setCompetitorUrl] = useState("");

  // Queries
  const { data: categories = [], isLoading: categoriesLoading } = useQuery({
    queryKey: ["categories"],
    queryFn: listCategories,
  });

  const { data: task } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => getTask(taskId!),
    enabled: taskId !== null,
    refetchInterval: taskId ? 3000 : false,
  });

  const { data: brand } = useQuery({
    queryKey: ["brand-profile"],
    queryFn: getBrandProfile,
  });

  // Derived state
  const currentStep: TaskStep = task?.current_step ?? "input";
  const candidates = task?.candidates ?? [];
  const taskStarted = taskId !== null;

  // Handlers
  const handleStartTask = useCallback(async () => {
    try {
      setSending(true);
      const config: Record<string, unknown> = {};
      if (activeEntry === "competitor_link" && competitorUrl) {
        config.source_url = competitorUrl;
      }
      if (sourceImagePath) {
        config.source_image_path = sourceImagePath;
      }
      const newTask = await createTask({
        entry_type: activeEntry,
        product_category_id: selectedCategoryId,
        task_config_json: config,
      });
      setTaskId(newTask.id);
      queryClient.invalidateQueries({ queryKey: QK.task(newTask.id) });
      message.success("任务已创建");
    } catch (err: unknown) {
      if (isNetworkError(err)) {
        message.error("网络连接失败，请检查网络后重试");
      } else {
        message.error(err instanceof Error ? err.message : "创建任务失败");
      }
    } finally {
      setSending(false);
    }
  }, [activeEntry, competitorUrl, sourceImagePath, selectedCategoryId, queryClient]);

  const handleSelectCandidate = useCallback(async (candidateId: number) => {
    if (!taskId) return;
    try {
      setSelecting(true);
      await selectCandidate(taskId, candidateId);
      queryClient.invalidateQueries({ queryKey: QK.task(taskId) });
    } catch (err: unknown) {
      if (isNetworkError(err)) {
        message.error("网络连接失败，请检查网络后重试");
      } else {
        const msg = err instanceof Error ? err.message : "选择失败";
        if (msg.includes("Cannot select candidate at step")) {
          message.warning("当前步骤不允许选择候选，正在刷新...");
          queryClient.invalidateQueries({ queryKey: QK.task(taskId) });
        } else {
          message.error(msg);
        }
      }
    } finally {
      setSelecting(false);
    }
  }, [taskId, queryClient]);

  const handleAdvance = useCallback(async () => {
    if (!taskId || !task) return;
    try {
      setAdvancing(true);
      // Pass current_step as expected_step for CAS concurrency control
      await advanceTask(taskId, undefined, task.current_step);
      queryClient.invalidateQueries({ queryKey: QK.task(taskId) });
      message.success("已推进到下一步");
    } catch (err: unknown) {
      if (isNetworkError(err)) {
        message.error("网络连接失败，请检查网络后重试");
      } else {
        const msg = err instanceof Error ? err.message : "推进失败";
        if (msg.includes("Conflict") || msg.includes("Illegal")) {
          message.warning("状态冲突，正在刷新...");
          queryClient.invalidateQueries({ queryKey: QK.task(taskId) });
        } else {
          message.error(msg);
        }
      }
    } finally {
      setAdvancing(false);
    }
  }, [taskId, task, queryClient]);

  const handleUpload = useCallback(async (file: File) => {
    try {
      const result = await uploadImage(file);
      setSourceImagePath(result.file_path);
      message.success("图片上传成功");
    } catch (err: unknown) {
      if (isNetworkError(err)) {
        message.error("网络连接失败，请检查网络后重试");
      } else {
        message.error(err instanceof Error ? err.message : "上传失败");
      }
    }
    return false; // prevent antd auto upload
  }, []);

  const handleSendChat = useCallback(async () => {
    if (!chatInput.trim()) return;
    const userMsg: ChatMessage = {
      id: Date.now(),
      project_id: 0,
      version_id: null,
      sender_type: "user",
      content: chatInput,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    // TODO: integrate with agent router when project is linked
  }, [chatInput]);

  // --- Render ---
  const isError = task?.status === "error";
  const isCancelled = task?.status === "cancelled";
  const isCompleted = task?.status === "completed";
  const isTerminal = isCancelled || isCompleted;
  const lastError = task?.task_config_json?.last_error as string | undefined;

  return (
    <div style={{ padding: "0 8px" }}>
      {/* Step bar */}
      <StepBar currentStep={currentStep} />

      {/* Error banner */}
      {isError && (
        <Card size="small" style={{ marginBottom: 12, borderColor: "#ff4d4f" }}>
          <Result
            status="warning"
            title="任务遇到错误"
            subTitle={lastError || "请重试或联系管理员"}
            extra={
              <Button type="primary" onClick={handleAdvance} loading={advancing}>
                重试当前步骤
              </Button>
            }
          />
        </Card>
      )}

      {/* Terminal state banner */}
      {isTerminal && (
        <Card size="small" style={{ marginBottom: 12 }}>
          <Result
            status={isCompleted ? "success" : "info"}
            title={isCompleted ? "任务已完成" : "任务已取消"}
          />
        </Card>
      )}

      {/* Entry tabs (only before task starts) */}
      {!taskStarted && (
        <EntryTabs activeEntry={activeEntry} onChange={setActiveEntry} disabled={taskStarted} />
      )}

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, minHeight: 500 }}>
        {/* Left column: input / chat */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Input area based on entry type and step */}
          {currentStep === "input" && !taskStarted && (
            <Card title="输入需求" size="small">
              {activeEntry === "competitor_link" && (
                <Input
                  placeholder="输入竞品链接（1688/淘宝/独立站）"
                  value={competitorUrl}
                  onChange={(e) => setCompetitorUrl(e.target.value)}
                  style={{ marginBottom: 12 }}
                />
              )}

              {(activeEntry === "white_bg_upload" || activeEntry === "image_scene_video") && (
                <Upload
                  accept="image/*"
                  showUploadList={false}
                  beforeUpload={handleUpload}
                  style={{ marginBottom: 12 }}
                >
                  <Button icon={<UploadOutlined />}>
                    {sourceImagePath ? "重新上传" : "上传产品图片"}
                  </Button>
                </Upload>
              )}

              <CategorySelector
                categories={categories}
                value={selectedCategoryId}
                onChange={setSelectedCategoryId}
                loading={categoriesLoading}
              />

              <Button
                type="primary"
                onClick={handleStartTask}
                loading={sending}
                style={{ marginTop: 12, width: "100%" }}
                disabled={
                  (activeEntry === "competitor_link" && !competitorUrl) ||
                  (activeEntry !== "competitor_link" && !sourceImagePath)
                }
              >
                开始任务
              </Button>
            </Card>
          )}

          {/* Product select step */}
          {currentStep === "product_select" && (
            <Card title="选择参考图" size="small">
              <CandidateGrid
                candidates={candidates}
                onSelect={handleSelectCandidate}
              />
              <Space style={{ marginTop: 12 }}>
                <CategorySelector
                  categories={categories}
                  value={selectedCategoryId ?? task?.product_category_id ?? undefined}
                  onChange={setSelectedCategoryId}
                  loading={categoriesLoading}
                />
                <Button
                  type="primary"
                  onClick={handleAdvance}
                  loading={advancing}
                  disabled={!candidates.some((c) => c.is_selected)}
                >
                  下一步：生成场景图
                </Button>
              </Space>
            </Card>
          )}

          {/* Scene generate / content extend / review steps */}
          {(currentStep === "scene_generate" || currentStep === "content_extend" || currentStep === "review_finalize") && (
            <Card title="操作" size="small">
              <Space>
                {currentStep !== "review_finalize" && (
                  <Button type="primary" onClick={handleAdvance} loading={advancing}>
                    下一步
                  </Button>
                )}
                {currentStep === "review_finalize" && (
                  <Button type="primary" loading={advancing} onClick={handleAdvance}>
                    定稿
                  </Button>
                )}
              </Space>
            </Card>
          )}

          {/* Chat panel (always visible when task started) */}
          {taskStarted && (
            <Card title="对话" size="small" style={{ flex: 1 }}>
              <ChatPanel
                messages={chatMessages}
                inputValue={chatInput}
                onInputChange={setChatInput}
                onSend={handleSendChat}
                sending={sending}
              />
            </Card>
          )}
        </div>

        {/* Right column: results / preview */}
        <Card title="预览" size="small">
          <ResultPanel candidates={candidates} />
        </Card>
      </div>
    </div>
  );
}
