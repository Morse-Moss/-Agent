import { useEffect, useMemo, useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Form, Image, Input, InputNumber, Select, Space, Typography, message } from "antd";
import type { FormInstance } from "antd";

import {
  applyProviderPreset,
  deleteProviderPreset,
  getApiKeys,
  getAssetUrl,
  getProviderPresets,
  getProviderSettings,
  saveApiKeys,
  saveProviderPreset,
  saveProviderSettings,
  testImageProvider,
  testLLMProvider,
} from "../lib/api";
import type { ProviderPreset, ProviderTestResult } from "../lib/types";

const llmProviderOptions = [
  { label: "本地演示模式（local_demo）", value: "local_demo" },
  { label: "智谱 GLM（zhipu_glm）", value: "zhipu_glm" },
  { label: "Codex 接口（codex_ai）", value: "codex_ai" },
];

const imageProviderOptions = [
  { label: "本地演示模式（local_demo）", value: "local_demo" },
  { label: "通义千问图片（qwen_image）", value: "qwen_image" },
  { label: "智谱图片（zhipu_image）", value: "zhipu_image" },
  { label: "通用 HTTP 图片接口（generic_http）", value: "generic_http" },
];

const sourceLabelMap: Record<string, string> = {
  env: "环境变量",
  db: "数据库",
  default: "默认值",
  unset: "未设置",
};

const llmQuickTemplates = [
  {
    name: "Codex 默认",
    values: {
      llm_provider: "codex_ai",
      llm_api_url: "https://cursor.scihub.edu.kg/openai",
      llm_model: "gpt-5-codex",
      llm_timeout_seconds: 120,
      llm_api_key_header: "Authorization",
    },
  },
  {
    name: "智谱 GLM 默认",
    values: {
      llm_provider: "zhipu_glm",
      llm_api_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions",
      llm_model: "glm-4.7",
      llm_timeout_seconds: 120,
      llm_api_key_header: "Authorization",
    },
  },
];

const imageQuickTemplates = [
  {
    name: "Qwen 默认",
    values: {
      image_provider: "qwen_image",
      image_api_url: "https://dashscope.aliyuncs.com/api/v1",
      image_model: "qwen-image-2.0",
      image_timeout_seconds: 120,
      image_api_key_header: "Authorization",
      cutout_provider: "local_demo",
    },
  },
  {
    name: "智谱图片默认",
    values: {
      image_provider: "zhipu_image",
      image_api_url: "https://open.bigmodel.cn/api/paas/v4/images/generations",
      image_model: "cogview-4-250304",
      image_timeout_seconds: 120,
      image_api_key_header: "Authorization",
      cutout_provider: "local_demo",
    },
  },
];

function renderProviderLabel(value: string, options: Array<{ label: string; value: string }>): string {
  return options.find((item) => item.value === value)?.label ?? value;
}

function renderSourceLabel(value: string): string {
  return sourceLabelMap[value] ?? value;
}

function presetDescription(preset: ProviderPreset): string {
  return [preset.provider, preset.model || "未设置模型", preset.api_url || "未设置地址"].join(" / ");
}

function findActivePreset(
  presets: ProviderPreset[],
  current: {
    provider: string;
    api_url: string | null;
    model: string | null;
    timeout_seconds: number;
    api_key_header: string;
  } | null,
): ProviderPreset | null {
  if (!current) {
    return null;
  }

  return (
    presets.find(
      (preset) =>
        preset.provider === current.provider &&
        (preset.api_url || "") === (current.api_url || "") &&
        (preset.model || "") === (current.model || "") &&
        preset.timeout_seconds === current.timeout_seconds &&
        preset.api_key_header === current.api_key_header,
    ) ?? null
  );
}

function applyPartialTemplate(form: FormInstance, values: Record<string, unknown>): void {
  form.setFieldsValue({
    ...form.getFieldsValue(),
    ...values,
  });
}

export function SettingsPage(): JSX.Element {
  const [keysForm] = Form.useForm();
  const [providerForm] = Form.useForm();
  const [llmPresetName, setLlmPresetName] = useState("");
  const [imagePresetName, setImagePresetName] = useState("");
  const [llmTestResult, setLlmTestResult] = useState<ProviderTestResult | null>(null);
  const [imageTestResult, setImageTestResult] = useState<ProviderTestResult | null>(null);
  const [testingLLM, setTestingLLM] = useState(false);
  const [testingImage, setTestingImage] = useState(false);
  const [savingLlmPreset, setSavingLlmPreset] = useState(false);
  const [savingImagePreset, setSavingImagePreset] = useState(false);
  const queryClient = useQueryClient();

  const apiKeysQuery = useQuery({
    queryKey: ["api-keys"],
    queryFn: getApiKeys,
  });

  const providerQuery = useQuery({
    queryKey: ["provider-settings"],
    queryFn: getProviderSettings,
  });

  const presetsQuery = useQuery({
    queryKey: ["provider-presets"],
    queryFn: getProviderPresets,
  });

  useEffect(() => {
    if (providerQuery.data) {
      providerForm.setFieldsValue(providerQuery.data);
    }
  }, [providerForm, providerQuery.data]);

  const currentSummary = useMemo(() => {
    if (!providerQuery.data) {
      return null;
    }
    return {
      llm: renderProviderLabel(providerQuery.data.llm_provider, llmProviderOptions),
      image: renderProviderLabel(providerQuery.data.image_provider, imageProviderOptions),
    };
  }, [providerQuery.data]);

  const activeLlmPreset = useMemo(
    () =>
      findActivePreset(
        presetsQuery.data?.llm_presets ?? [],
        providerQuery.data
          ? {
              provider: providerQuery.data.llm_provider,
              api_url: providerQuery.data.llm_api_url,
              model: providerQuery.data.llm_model,
              timeout_seconds: providerQuery.data.llm_timeout_seconds,
              api_key_header: providerQuery.data.llm_api_key_header,
            }
          : null,
      ),
    [presetsQuery.data, providerQuery.data],
  );

  const activeImagePreset = useMemo(
    () =>
      findActivePreset(
        presetsQuery.data?.image_presets ?? [],
        providerQuery.data
          ? {
              provider: providerQuery.data.image_provider,
              api_url: providerQuery.data.image_api_url,
              model: providerQuery.data.image_model,
              timeout_seconds: providerQuery.data.image_timeout_seconds,
              api_key_header: providerQuery.data.image_api_key_header,
            }
          : null,
      ),
    [presetsQuery.data, providerQuery.data],
  );

  async function refreshSettings(): Promise<void> {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["api-keys"] }),
      queryClient.invalidateQueries({ queryKey: ["provider-settings"] }),
      queryClient.invalidateQueries({ queryKey: ["provider-presets"] }),
    ]);
  }

  async function savePreset(scope: "llm" | "image"): Promise<void> {
    const values = providerForm.getFieldsValue();
    const presetName = scope === "llm" ? llmPresetName.trim() : imagePresetName.trim();
    if (!presetName) {
      message.error("请先输入预设名称。");
      return;
    }

    try {
      if (scope === "llm") {
        setSavingLlmPreset(true);
        await saveProviderPreset({
          scope,
          preset_name: presetName,
          provider: values.llm_provider,
          api_url: values.llm_api_url,
          model: values.llm_model,
          timeout_seconds: values.llm_timeout_seconds,
          api_key_header: values.llm_api_key_header,
          include_api_key: true,
        });
        setLlmPresetName("");
      } else {
        setSavingImagePreset(true);
        await saveProviderPreset({
          scope,
          preset_name: presetName,
          provider: values.image_provider,
          api_url: values.image_api_url,
          model: values.image_model,
          timeout_seconds: values.image_timeout_seconds,
          api_key_header: values.image_api_key_header,
          include_api_key: true,
        });
        setImagePresetName("");
      }

      await refreshSettings();
      message.success("预设已保存，后续可以一键切换。");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存预设失败");
    } finally {
      setSavingLlmPreset(false);
      setSavingImagePreset(false);
    }
  }

  async function applyPreset(scope: "llm" | "image", presetName: string): Promise<void> {
    try {
      await applyProviderPreset({ scope, preset_name: presetName });
      await refreshSettings();
      message.success(`已应用预设：${presetName}`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "应用预设失败");
    }
  }

  async function removePreset(scope: "llm" | "image", presetName: string): Promise<void> {
    try {
      await deleteProviderPreset({ scope, preset_name: presetName });
      await refreshSettings();
      message.success(`已删除预设：${presetName}`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "删除预设失败");
    }
  }

  return (
    <div className="page-grid">
      <Card className="page-hero-card">
        <Space direction="vertical" size={6}>
          <Typography.Text className="page-kicker">Gateway Settings</Typography.Text>
          <Typography.Title level={3} style={{ margin: 0 }}>
            系统设置
          </Typography.Title>
          <Typography.Text type="secondary">
            这里可以管理 LLM 和图片模型的当前配置、快速模板以及可复用预设。预设会连同当前 Key 一起保存，后续切换时不需要再重复填写模型名、URL 和密钥。
          </Typography.Text>
          {currentSummary ? (
            <Typography.Text type="secondary">
              当前生效：LLM 为 {currentSummary.llm}，图片为 {currentSummary.image}。
            </Typography.Text>
          ) : null}
          <Typography.Text type="secondary">
            当前预设：LLM 为 {activeLlmPreset?.preset_name ?? "未匹配到已保存预设"}，图片为{" "}
            {activeImagePreset?.preset_name ?? "未匹配到已保存预设"}。
          </Typography.Text>
        </Space>
      </Card>

      <Card className="surface-card" loading={apiKeysQuery.isLoading}>
        <Typography.Title level={4}>API Key 配置</Typography.Title>
        {apiKeysQuery.data ? (
          <Space direction="vertical" size={6} style={{ marginBottom: 18 }}>
            <Typography.Text type="secondary">
              LLM：{apiKeysQuery.data.llm_api_key ?? "未配置"}（来源：{renderSourceLabel(apiKeysQuery.data.llm_api_key_source)}）
            </Typography.Text>
            <Typography.Text type="secondary">
              生图：{apiKeysQuery.data.image_api_key ?? "未配置"}（来源：{renderSourceLabel(apiKeysQuery.data.image_api_key_source)}）
            </Typography.Text>
            <Typography.Text type="secondary">
              抠图：{apiKeysQuery.data.cutout_api_key ?? "未配置"}（来源：{renderSourceLabel(apiKeysQuery.data.cutout_api_key_source)}）
            </Typography.Text>
          </Space>
        ) : null}

        <Form
          layout="vertical"
          form={keysForm}
          onFinish={async (values) => {
            try {
              await saveApiKeys(values);
              await queryClient.invalidateQueries({ queryKey: ["api-keys"] });
              keysForm.resetFields();
              message.success("API Key 已保存。");
            } catch (error) {
              message.error(error instanceof Error ? error.message : "保存失败");
            }
          }}
        >
          <Form.Item label="LLM 接口密钥" name="llm_api_key">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
          <Form.Item label="生图接口密钥" name="image_api_key">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
          <Form.Item label="抠图接口密钥" name="cutout_api_key">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
          <Button type="primary" htmlType="submit">
            保存 API Key
          </Button>
        </Form>
      </Card>

      <Card className="surface-card" loading={providerQuery.isLoading || presetsQuery.isLoading}>
        <Typography.Title level={4}>模型与接口配置</Typography.Title>
        <Typography.Paragraph type="secondary">
          你可以先点击下面的快速模板填入推荐参数，再保存成自己的专属预设。以后切换时直接点击“应用预设”即可，不用再手填一堆字段。
        </Typography.Paragraph>

        <Form
          layout="vertical"
          form={providerForm}
          onFinish={async (values) => {
            try {
              await saveProviderSettings(values);
              await queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
              message.success("当前模型与接口配置已保存。");
            } catch (error) {
              message.error(error instanceof Error ? error.message : "保存失败");
            }
          }}
        >
          <Typography.Title level={5}>LLM 配置</Typography.Title>
          <Space wrap style={{ marginBottom: 12 }}>
            {llmQuickTemplates.map((template) => (
              <Button
                key={template.name}
                onClick={() => {
                  applyPartialTemplate(providerForm, template.values);
                  message.success(`已填入模板：${template.name}`);
                }}
              >
                {template.name}
              </Button>
            ))}
          </Space>

          <Form.Item label="LLM Provider" name="llm_provider" rules={[{ required: true, message: "请选择 LLM Provider" }]}>
            <Select options={llmProviderOptions} />
          </Form.Item>
          <Form.Item label="LLM API URL" name="llm_api_url">
            <Input placeholder="例如：https://open.bigmodel.cn/api/paas/v4/chat/completions" />
          </Form.Item>
          <Form.Item label="LLM Model" name="llm_model">
            <Input placeholder="例如：glm-4.7 或 gpt-5-codex" />
          </Form.Item>
          <Form.Item label="LLM 超时时间（秒）" name="llm_timeout_seconds" rules={[{ required: true, message: "请输入超时时间" }]}>
            <InputNumber min={5} max={300} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="LLM 鉴权请求头名称" name="llm_api_key_header" rules={[{ required: true, message: "请输入鉴权 Header 名称" }]}>
            <Input placeholder="通常使用 Authorization" />
          </Form.Item>

          <Space wrap style={{ marginBottom: 18 }}>
            <Input
              value={llmPresetName}
              onChange={(event) => setLlmPresetName(event.target.value)}
              placeholder="输入 LLM 预设名称，例如：Codex 正式环境"
              style={{ width: 280 }}
            />
            <Button loading={savingLlmPreset} onClick={() => void savePreset("llm")}>
              保存当前为 LLM 预设
            </Button>
          </Space>

          <Card size="small" className="surface-card" style={{ marginBottom: 24 }}>
            <Typography.Text strong>已保存的 LLM 预设</Typography.Text>
            <Space direction="vertical" size={12} style={{ display: "flex", marginTop: 12 }}>
              {(presetsQuery.data?.llm_presets ?? []).length ? (
                presetsQuery.data?.llm_presets.map((preset) => (
                  <Card key={`llm-${preset.preset_name}`} size="small">
                    <Space direction="vertical" size={6} style={{ display: "flex" }}>
                      <Typography.Text strong>
                        {preset.preset_name}
                        {activeLlmPreset?.preset_name === preset.preset_name ? "（当前生效）" : ""}
                      </Typography.Text>
                      <Typography.Text type="secondary">{presetDescription(preset)}</Typography.Text>
                      <Typography.Text type="secondary">
                        {preset.has_api_key ? "预设已保存密钥，切换时会一并恢复。" : "预设未保存密钥，应用后会保留当前密钥。"}
                      </Typography.Text>
                      <Space wrap>
                        <Button onClick={() => void applyPreset("llm", preset.preset_name)}>应用预设</Button>
                        <Button danger onClick={() => void removePreset("llm", preset.preset_name)}>
                          删除
                        </Button>
                      </Space>
                    </Space>
                  </Card>
                ))
              ) : (
                <Typography.Text type="secondary">还没有保存任何 LLM 预设。</Typography.Text>
              )}
            </Space>
          </Card>

          <Typography.Title level={5}>图片与图像接口配置</Typography.Title>
          <Space wrap style={{ marginBottom: 12 }}>
            {imageQuickTemplates.map((template) => (
              <Button
                key={template.name}
                onClick={() => {
                  applyPartialTemplate(providerForm, template.values);
                  message.success(`已填入模板：${template.name}`);
                }}
              >
                {template.name}
              </Button>
            ))}
          </Space>

          <Form.Item label="图片 Provider" name="image_provider" rules={[{ required: true, message: "请选择图片 Provider" }]}>
            <Select options={imageProviderOptions} />
          </Form.Item>
          <Form.Item label="抠图 Provider" name="cutout_provider" rules={[{ required: true, message: "请选择抠图 Provider" }]}>
            <Select options={[{ label: "本地演示模式（local_demo）", value: "local_demo" }]} />
          </Form.Item>
          <Form.Item label="图片 API URL" name="image_api_url">
            <Input placeholder="例如：https://dashscope.aliyuncs.com/api/v1" />
          </Form.Item>
          <Form.Item label="图片 Model" name="image_model">
            <Input placeholder="例如：qwen-image-2.0 或 cogview-4-250304" />
          </Form.Item>
          <Form.Item label="图片超时时间（秒）" name="image_timeout_seconds" rules={[{ required: true, message: "请输入超时时间" }]}>
            <InputNumber min={5} max={300} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="图片鉴权请求头名称"
            name="image_api_key_header"
            rules={[{ required: true, message: "请输入鉴权 Header 名称" }]}
          >
            <Input placeholder="通常使用 Authorization" />
          </Form.Item>

          <Space wrap style={{ marginBottom: 18 }}>
            <Input
              value={imagePresetName}
              onChange={(event) => setImagePresetName(event.target.value)}
              placeholder="输入图片预设名称，例如：Qwen 正式环境"
              style={{ width: 280 }}
            />
            <Button loading={savingImagePreset} onClick={() => void savePreset("image")}>
              保存当前为图片预设
            </Button>
          </Space>

          <Card size="small" className="surface-card" style={{ marginBottom: 24 }}>
            <Typography.Text strong>已保存的图片预设</Typography.Text>
            <Space direction="vertical" size={12} style={{ display: "flex", marginTop: 12 }}>
              {(presetsQuery.data?.image_presets ?? []).length ? (
                presetsQuery.data?.image_presets.map((preset) => (
                  <Card key={`image-${preset.preset_name}`} size="small">
                    <Space direction="vertical" size={6} style={{ display: "flex" }}>
                      <Typography.Text strong>
                        {preset.preset_name}
                        {activeImagePreset?.preset_name === preset.preset_name ? "（当前生效）" : ""}
                      </Typography.Text>
                      <Typography.Text type="secondary">{presetDescription(preset)}</Typography.Text>
                      <Typography.Text type="secondary">
                        {preset.has_api_key ? "预设已保存密钥，切换时会一并恢复。" : "预设未保存密钥，应用后会保留当前密钥。"}
                      </Typography.Text>
                      <Space wrap>
                        <Button onClick={() => void applyPreset("image", preset.preset_name)}>应用预设</Button>
                        <Button danger onClick={() => void removePreset("image", preset.preset_name)}>
                          删除
                        </Button>
                      </Space>
                    </Space>
                  </Card>
                ))
              ) : (
                <Typography.Text type="secondary">还没有保存任何图片预设。</Typography.Text>
              )}
            </Space>
          </Card>

          <Space wrap>
            <Button type="primary" htmlType="submit">
              保存当前模型与接口配置
            </Button>
            <Button
              loading={testingLLM}
              onClick={async () => {
                try {
                  setTestingLLM(true);
                  await saveProviderSettings(providerForm.getFieldsValue());
                  const result = await testLLMProvider();
                  setLlmTestResult(result);
                  message.success(result.ok ? "LLM Provider 测试成功。" : "LLM Provider 测试失败。");
                  await queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
                } catch (error) {
                  message.error(error instanceof Error ? error.message : "测试失败");
                } finally {
                  setTestingLLM(false);
                }
              }}
            >
              测试 LLM 接口
            </Button>
            <Button
              loading={testingImage}
              onClick={async () => {
                try {
                  setTestingImage(true);
                  await saveProviderSettings(providerForm.getFieldsValue());
                  const result = await testImageProvider();
                  setImageTestResult(result);
                  message.success(result.ok ? "图片 Provider 测试成功。" : "图片 Provider 测试失败。");
                  await queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
                } catch (error) {
                  message.error(error instanceof Error ? error.message : "测试失败");
                } finally {
                  setTestingImage(false);
                }
              }}
            >
              测试生图接口
            </Button>
          </Space>
        </Form>

        {llmTestResult ? (
          <Card size="small" className="surface-card" style={{ marginTop: 18 }}>
            <Space direction="vertical" size={8}>
              <Typography.Text strong>最近一次 LLM 测试结果</Typography.Text>
              <Typography.Text>{`Provider：${renderProviderLabel(llmTestResult.provider, llmProviderOptions)} / ${llmTestResult.detail}`}</Typography.Text>
            </Space>
          </Card>
        ) : null}

        {imageTestResult ? (
          <Card size="small" className="surface-card" style={{ marginTop: 18 }}>
            <Space direction="vertical" size={8}>
              <Typography.Text strong>最近一次图片测试结果</Typography.Text>
              <Typography.Text>{`Provider：${renderProviderLabel(imageTestResult.provider, imageProviderOptions)} / ${imageTestResult.detail}`}</Typography.Text>
              {imageTestResult.file_path ? <Image src={getAssetUrl(imageTestResult.file_path)} width={240} /> : null}
            </Space>
          </Card>
        ) : null}
      </Card>
    </div>
  );
}
