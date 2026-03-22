import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Empty, Popconfirm, Select, Space, Typography, message } from "antd";
import { Link, useSearchParams } from "react-router-dom";

import { StatusTag } from "../components/StatusTag";
import { deleteProject, getAssetUrl, listProjects } from "../lib/api";

const platformLabelMap: Record<string, string> = {
  taobao: "淘宝",
};

const pageTypeLabelMap: Record<string, string> = {
  main_image: "淘宝主图",
  detail_module: "详情页模块图",
  banner: "品牌 Banner",
};

const filters = [
  { label: "全部状态", value: "" },
  { label: "未审核", value: "unreviewed" },
  { label: "已通过", value: "approved" },
  { label: "已驳回", value: "rejected" },
  { label: "已定稿", value: "finalized" },
];

export function ProjectsPage(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const currentFilter = searchParams.get("status") ?? "";

  const query = useQuery({
    queryKey: ["projects", currentFilter],
    queryFn: () => listProjects(currentFilter || undefined),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      message.success("作品已删除");
    },
    onError: (error) => {
      message.error(error instanceof Error ? error.message : "删除失败");
    },
  });

  return (
    <div className="page-grid">
      <Card className="page-hero-card">
        <Space direction="vertical" size={4}>
          <Typography.Text className="page-kicker">Project Gallery</Typography.Text>
          <Typography.Title level={3} style={{ margin: 0 }}>
            作品列表
          </Typography.Title>
          <Typography.Text type="secondary">
            直接查看每个项目的当前封面、状态、最新版本和创建时间，便于快速筛选与回到详情页继续处理。
          </Typography.Text>
        </Space>
        <div style={{ marginTop: 18 }}>
          <Select
            value={currentFilter}
            style={{ width: 220 }}
            options={filters}
            onChange={(value) => {
              if (value) {
                setSearchParams({ status: value });
              } else {
                setSearchParams({});
              }
            }}
          />
        </div>
      </Card>

      {query.data && query.data.length > 0 ? (
        <div className="project-grid">
          {query.data.map((project) => (
            <Card hoverable className="project-card" key={project.id}>
              <div className="project-cover">
                {project.cover_asset_path ? (
                  <img src={getAssetUrl(project.cover_asset_path)} alt={project.name} className="project-cover-image" />
                ) : (
                  <div className="project-cover-placeholder">
                    <span>{pageTypeLabelMap[project.page_type] ?? "等待生成封面"}</span>
                  </div>
                )}
              </div>
              <div className="project-card-body">
                <Space align="start" style={{ width: "100%", justifyContent: "space-between" }}>
                  <div>
                    <Typography.Title level={4} style={{ margin: 0 }}>
                      {project.name}
                    </Typography.Title>
                    <Typography.Text type="secondary">{project.product_name || "待补充产品名称"}</Typography.Text>
                  </div>
                  <StatusTag status={project.status} />
                </Space>

                <div className="project-meta-list">
                  <div className="project-meta-item">
                    <span className="project-meta-label">页面类型</span>
                    <span>{pageTypeLabelMap[project.page_type] ?? project.page_type}</span>
                  </div>
                  <div className="project-meta-item">
                    <span className="project-meta-label">平台</span>
                    <span>{platformLabelMap[project.platform] ?? project.platform}</span>
                  </div>
                  <div className="project-meta-item">
                    <span className="project-meta-label">最新版本</span>
                    <span>{project.latest_version_no ? `V${project.latest_version_no}` : "暂无版本"}</span>
                  </div>
                  <div className="project-meta-item">
                    <span className="project-meta-label">创建时间</span>
                    <span>{new Date(project.created_at).toLocaleString("zh-CN")}</span>
                  </div>
                </div>

                <div className="project-card-actions">
                  <Link to={`/projects/${project.id}`}>
                    <Button type="primary">查看详情</Button>
                  </Link>
                  <Popconfirm
                    title="确认删除这个作品吗？"
                    description="删除后会同时移除项目、版本记录、聊天消息和关联图片文件。"
                    okText="确认删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
                    onConfirm={() => deleteMutation.mutate(project.id)}
                  >
                    <Button danger loading={deleteMutation.isPending && deleteMutation.variables === project.id}>
                      删除
                    </Button>
                  </Popconfirm>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="surface-card">
          {query.isLoading ? (
            <Typography.Text>正在加载作品列表...</Typography.Text>
          ) : (
            <Empty description="还没有作品，先去创作工作台生成第一版主图吧。" />
          )}
        </Card>
      )}
    </div>
  );
}
