import { Button, Layout, Menu, Typography } from "antd";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { clearAuthToken } from "../lib/auth";

const { Header, Sider, Content } = Layout;

const navigationItems = [
  { key: "/create", label: <Link to="/create">创作工作台</Link> },
  { key: "/projects", label: <Link to="/projects">作品列表</Link> },
  { key: "/brand", label: <Link to="/brand">品牌资料</Link> },
  { key: "/settings", label: <Link to="/settings">系统设置</Link> },
];

export function AppShell(): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const selectedKey = location.pathname.startsWith("/projects/") ? "/projects" : location.pathname;

  return (
    <Layout className="app-shell">
      <Sider className="app-sider" width={248}>
        <div className="brand-block">
          <Typography.Text className="brand-eyebrow">E-COMMERCE VISUAL AGENT</Typography.Text>
          <Typography.Title level={3} className="brand-title">
            电商美工 Agent
          </Typography.Title>
          <Typography.Paragraph className="brand-copy">
            围绕主图创作、版本迭代、审核定稿和品牌资料管理的一体化工作台。
          </Typography.Paragraph>
        </div>
        <Menu selectedKeys={[selectedKey]} items={navigationItems} theme="dark" className="app-menu" />
      </Sider>
      <Layout>
        <Header className="app-header">
          <div>
            <Typography.Text className="header-kicker">企业内部创意工作台</Typography.Text>
            <Typography.Title level={4} className="header-title">
              广告材料视觉生产中枢
            </Typography.Title>
          </div>
          <Button
            onClick={() => {
              clearAuthToken();
              navigate("/login");
            }}
          >
            退出登录
          </Button>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
