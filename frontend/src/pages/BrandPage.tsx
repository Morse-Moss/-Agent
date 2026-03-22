import { useEffect } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Form, Input, Space, Typography, message } from "antd";

import { getBrandProfile, saveBrandProfile, summarizeBrand } from "../lib/api";

export function BrandPage(): JSX.Element {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const brandQuery = useQuery({
    queryKey: ["brand-profile"],
    queryFn: getBrandProfile,
  });

  useEffect(() => {
    if (brandQuery.data) {
      form.setFieldsValue({
        ...brandQuery.data,
        recommended_keywords: brandQuery.data.recommended_keywords.join(", "),
      });
    }
  }, [brandQuery.data, form]);

  return (
    <div className="page-grid">
      <Card className="page-hero-card">
        <Space direction="vertical" size={6}>
          <Typography.Text className="page-kicker">Brand Context</Typography.Text>
          <Typography.Title level={3} style={{ margin: 0 }}>
            品牌资料与风格总结
          </Typography.Title>
          <Typography.Text type="secondary">
            首期采用单品牌空间，当前资料会默认参与每次创作，用于补齐品牌描述、风格摘要和推荐关键词。
          </Typography.Text>
        </Space>
      </Card>

      <Card className="surface-card" loading={brandQuery.isLoading}>
        <Form
          layout="vertical"
          form={form}
          onFinish={async (values) => {
            try {
              await saveBrandProfile({
                ...values,
                recommended_keywords: String(values.recommended_keywords ?? "")
                  .split(/[,\n]/)
                  .map((item) => item.trim())
                  .filter(Boolean),
              });
              await queryClient.invalidateQueries({ queryKey: ["brand-profile"] });
              message.success("品牌资料已保存");
            } catch (error) {
              message.error(error instanceof Error ? error.message : "保存失败");
            }
          }}
        >
          <Form.Item label="品牌名称" name="name" rules={[{ required: true, message: "请输入品牌名称" }]}>
            <Input size="large" />
          </Form.Item>
          <Form.Item label="品牌描述" name="description" rules={[{ required: true, message: "请输入品牌描述" }]}>
            <Input.TextArea rows={6} placeholder="请填写品牌定位、产品特点、目标客户和表达偏好。" />
          </Form.Item>
          <Form.Item label="风格总结" name="style_summary">
            <Input.TextArea rows={4} placeholder="例如：工业高级感、金属质感明确、画面简洁、强调材料品质与定制能力。" />
          </Form.Item>
          <Form.Item label="推荐关键词" name="recommended_keywords">
            <Input.TextArea rows={3} placeholder="多个关键词请用逗号分隔，例如：工业简洁，金属质感，耐腐蚀，支持定制" />
          </Form.Item>
          <Space wrap>
            <Button
              onClick={async () => {
                try {
                  const description = String(form.getFieldValue("description") ?? "");
                  if (!description.trim()) {
                    message.warning("请先填写品牌描述，再生成风格总结。");
                    return;
                  }
                  const summary = await summarizeBrand({ description });
                  form.setFieldsValue({
                    style_summary: summary.style_summary,
                    recommended_keywords: summary.recommended_keywords.join(", "),
                  });
                  message.success("已生成品牌风格总结。");
                } catch (error) {
                  message.error(error instanceof Error ? error.message : "生成失败");
                }
              }}
            >
              生成总结
            </Button>
            <Button type="primary" htmlType="submit">
              保存品牌资料
            </Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
