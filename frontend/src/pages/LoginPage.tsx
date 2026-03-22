import { Button, Card, Form, Input, Space, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";

import { login } from "../lib/api";
import { setAuthToken } from "../lib/auth";

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();

  return (
    <div className="login-page">
      <div className="login-stage">
        <div className="login-hero login-hero-compact">
          <Typography.Text className="brand-eyebrow">E-COMMERCE VISUAL AGENT</Typography.Text>
          <Typography.Title className="login-hero-title login-hero-title-compact" level={2}>
            电商美工 Agent
          </Typography.Title>
          <Typography.Paragraph className="login-hero-copy login-hero-copy-compact">
            企业内部电商视觉创作工作台，聚焦主图生成、版本迭代与审核定稿。
          </Typography.Paragraph>
        </div>

        <Card className="login-card login-card-centered">
          <Typography.Text className="login-card-kicker">欢迎回来</Typography.Text>
          <Typography.Title level={3}>登录系统</Typography.Title>
          <Typography.Paragraph type="secondary">使用默认管理员账号即可进入工作台。</Typography.Paragraph>
          <Space wrap className="login-credentials">
            <Typography.Text>默认账号：admin</Typography.Text>
            <Typography.Text>默认密码：admin123</Typography.Text>
          </Space>
          <Form
            layout="vertical"
            initialValues={{ username: "admin", password: "admin123" }}
            onFinish={async (values) => {
              try {
                const result = await login(values.username, values.password);
                setAuthToken(result.access_token);
                message.success("登录成功");
                navigate("/create");
              } catch (error) {
                message.error(error instanceof Error ? error.message : "登录失败");
              }
            }}
          >
            <Form.Item label="用户名" name="username" rules={[{ required: true, message: "请输入用户名" }]}>
              <Input autoComplete="username" />
            </Form.Item>
            <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
              <Input.Password autoComplete="current-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" block>
              进入工作台
            </Button>
          </Form>
        </Card>
      </div>
    </div>
  );
}
