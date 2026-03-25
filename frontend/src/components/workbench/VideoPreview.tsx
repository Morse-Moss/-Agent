import { Empty, Typography } from "antd";

interface VideoPreviewProps {
  videoUrl?: string | null;
  status?: string;
  error?: string;
}

export function VideoPreview({ videoUrl, status, error }: VideoPreviewProps): JSX.Element {
  if (error) {
    return <Typography.Text type="danger">{error}</Typography.Text>;
  }

  if (status === "processing" || status === "pending") {
    return <Typography.Text type="secondary">视频生成中，请稍候...</Typography.Text>;
  }

  if (!videoUrl) {
    return <Empty description="暂无视频" />;
  }

  return (
    <div style={{ textAlign: "center" }}>
      <video
        src={videoUrl}
        controls
        style={{ maxWidth: "100%", borderRadius: 8 }}
      />
    </div>
  );
}
