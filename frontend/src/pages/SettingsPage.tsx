import { useEffect, useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Form, Image, Input, InputNumber, Select, Space, Typography, message } from "antd";

import { getApiKeys, getAssetUrl, getProviderSettings, saveApiKeys, saveProviderSettings, testImageProvider } from "../lib/api";
import type { ProviderTestResult } from "../lib/types";

const providerOptions = [
  { label: "本地演示模式（local_demo）", value: "local_demo" },
  { label: "通用 HTTP 生图接口（generic_http）", value: "generic_http" },
  { label: "OpenAI 兼容接口（openai_compatible）", value: "openai_compatible" },
  { label: "通义千问生图（qwen_image）", value: "qwen_image" },
];

const sourceLabelMap: Record<string, string> = {
  env: "环境变量",
  db: "数据库",
  default: "默认值",
  unset: "未设置",
};

function renderProviderLabel(value: string): string {
  return providerOptions.find((item) => item.value === value)?.label ?? value;
}

function renderSourceLabel(value: string): string {
  return sourceLabelMap[value] ?? value;
}

export function SettingsPage(): JSX.Element {
  const [keysForm] = Form.useForm();
  const [providerForm] = Form.useForm();
  const [providerTestResult, setProviderTestResult] = useState<ProviderTestResult | null>(null);
  const [testingProvider, setTestingProvider] = useState(false);
  const queryClient = useQueryClient();
  const apiKeysQuery = useQuery({
    queryKey: ["api-keys"],
    queryFn: getApiKeys,
  });
  const providerQuery = useQuery({
    queryKey: ["provider-settings"],
    queryFn: getProviderSettings,
  });

  useEffect(() => {
    if (providerQuery.data) {
      providerForm.setFieldsValue(providerQuery.data);
    }
  }, [providerForm, providerQuery.data]);

  return (
    <div className="page-grid">
      <Card className="page-hero-card">
        <Space direction="vertical" size={6}>
          <Typography.Text className="page-kicker">Gateway Settings</Typography.Text>
          <Typography.Title level={3} style={{ margin: 0 }}>
            系统设置
          </Typography.Title>
          <Typography.Text type="secondary">
            在这里统一管理 API Key 与 Provider 参数。当前系统已经适配通义千问生图接口，可直接配置后测试。
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

      <Card className="surface-card" loading={providerQuery.isLoading}>
        <Typography.Title level={4}>模型与接口配置</Typography.Title>
        <Typography.Paragraph type="secondary">
          如果接入通义千问生图，建议设置为：Image Provider = qwen_image，Image Model = qwen-image-2.0，
          Image API URL = https://dashscope.aliyuncs.com/api/v1，Image API Key Header = Authorization。
        </Typography.Paragraph>
        {providerQuery.data ? (
          <Space direction="vertical" size={6} style={{ marginBottom: 18 }}>
            <Typography.Text type="secondary">
              LLM 模式：{renderProviderLabel(providerQuery.data.llm_provider)}（来源：{renderSourceLabel(providerQuery.data.llm_provider_source)}）
            </Typography.Text>
            <Typography.Text type="secondary">
              生图模式：{renderProviderLabel(providerQuery.data.image_provider)}（来源：{renderSourceLabel(providerQuery.data.image_provider_source)}）
            </Typography.Text>
            <Typography.Text type="secondary">
              生图接口地址：{providerQuery.data.image_api_url || "未配置"}（来源：{renderSourceLabel(providerQuery.data.image_api_url_source)}）
            </Typography.Text>
            <Typography.Text type="secondary">
              生图模型：{providerQuery.data.image_model || "未配置"}（来源：{renderSourceLabel(providerQuery.data.image_model_source)}）
            </Typography.Text>
          </Space>
        ) : null}

        <Form
          layout="vertical"
          form={providerForm}
          onFinish={async (values) => {
            try {
              await saveProviderSettings(values);
              await queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
              message.success("模型与接口配置已保存。");
            } catch (error) {
              message.error(error instanceof Error ? error.message : "保存失败");
            }
          }}
        >
          <Form.Item label="LLM 模式" name="llm_provider" rules={[{ required: true, message: "请选择 LLM 模式" }]}>
            <Select options={[{ label: "本地演示模式（local_demo）", value: "local_demo" }]} />
          </Form.Item>
          <Form.Item label="生图模式" name="image_provider" rules={[{ required: true, message: "请选择生图模式" }]}>
            <Select options={providerOptions} />
          </Form.Item>
          <Form.Item label="抠图模式" name="cutout_provider" rules={[{ required: true, message: "请选择抠图模式" }]}>
            <Select options={[{ label: "本地演示模式（local_demo）", value: "local_demo" }]} />
          </Form.Item>
          <Form.Item label="生图接口地址" name="image_api_url">
            <Input placeholder="例如：https://dashscope.aliyuncs.com/api/v1" />
          </Form.Item>
          <Form.Item label="生图模型名" name="image_model">
            <Input placeholder="例如：qwen-image-2.0" />
          </Form.Item>
          <Form.Item label="生图超时时间（秒）" name="image_timeout_seconds" rules={[{ required: true, message: "请输入超时时间" }]}>
            <InputNumber min={5} max={300} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="鉴权请求头名称" name="image_api_key_header" rules={[{ required: true, message: "请输入鉴权 Header 名称" }]}>
            <Input placeholder="通义千问建议使用 Authorization" />
          </Form.Item>
          <Space wrap>
            <Button type="primary" htmlType="submit">
              保存模型与接口配置
            </Button>
            <Button
              loading={testingProvider}
              onClick={async () => {
                try {
                  setTestingProvider(true);
                  await saveProviderSettings(providerForm.getFieldsValue());
                  const result = await testImageProvider();
                  setProviderTestResult(result);
                  message.success(result.ok ? "生图 Provider 测试成功。" : "生图 Provider 测试失败。");
                  await queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
                } catch (error) {
                  message.error(error instanceof Error ? error.message : "测试失败");
                } finally {
                  setTestingProvider(false);
                }
              }}
            >
              测试生图接口
            </Button>
          </Space>
        </Form>

        {providerTestResult ? (
          <Card size="small" className="surface-card" style={{ marginTop: 18 }}>
            <Space direction="vertical" size={8}>
              <Typography.Text strong>最近一次测试结果</Typography.Text>
              <Typography.Text type={providerTestResult.ok ? "success" : "danger"}>
                Provider：{renderProviderLabel(providerTestResult.provider)} / {providerTestResult.detail}
              </Typography.Text>
              {providerTestResult.file_path ? <Image src={getAssetUrl(providerTestResult.file_path)} width={240} /> : null}
            </Space>
          </Card>
        ) : null}
      </Card>
    </div>
  );
}
