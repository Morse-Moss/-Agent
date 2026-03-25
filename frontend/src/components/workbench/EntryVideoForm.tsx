import { Button, Card, Checkbox, Form, Input, InputNumber, Radio, Space, message } from "antd";
import { useState } from "react";

interface EntryVideoFormProps {
  onSubmit: (params: VideoParams) => void;
  loading?: boolean;
}

export interface VideoParams {
  prompt: string;
  duration_seconds: number;
  orientation: "landscape" | "portrait";
  resolution: string;
  platforms: string[];
}

const PLATFORMS = ["Instagram", "TikTok", "Facebook", "X", "Pinterest"];

export function EntryVideoForm({ onSubmit, loading }: EntryVideoFormProps): JSX.Element {
  const [form] = Form.useForm();

  const handleFinish = (values: Record<string, unknown>) => {
    onSubmit({
      prompt: (values.prompt as string) || "",
      duration_seconds: (values.duration_seconds as number) || 5,
      orientation: (values.orientation as "landscape" | "portrait") || "landscape",
      resolution: (values.resolution as string) || "1080p",
      platforms: (values.platforms as string[]) || PLATFORMS,
    });
  };

  return (
    <Form form={form} layout="vertical" onFinish={handleFinish} initialValues={{
      duration_seconds: 5,
      orientation: "landscape",
      resolution: "1080p",
      platforms: PLATFORMS,
    }}>
      <Form.Item name="prompt" label="场景描述" rules={[{ required: true, message: "请输入场景描述" }]}>
        <Input.TextArea rows={3} placeholder="描述你想要的视频场景..." />
      </Form.Item>

      <Form.Item name="duration_seconds" label="视频时长（秒）">
        <InputNumber min={3} max={30} />
      </Form.Item>

      <Form.Item name="orientation" label="视频方向">
        <Radio.Group>
          <Radio value="landscape">横版</Radio>
          <Radio value="portrait">竖版</Radio>
        </Radio.Group>
      </Form.Item>

      <Form.Item name="resolution" label="清晰度">
        <Radio.Group>
          <Radio value="720p">720p</Radio>
          <Radio value="1080p">1080p</Radio>
          <Radio value="4k">4K</Radio>
        </Radio.Group>
      </Form.Item>

      <Form.Item name="platforms" label="文案平台">
        <Checkbox.Group options={PLATFORMS.map((p) => ({ label: p, value: p }))} />
      </Form.Item>

      <Button type="primary" htmlType="submit" loading={loading} block>
        生成视频 + 文案
      </Button>
    </Form>
  );
}
