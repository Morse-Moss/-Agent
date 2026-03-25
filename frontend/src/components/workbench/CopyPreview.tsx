import { Button, Card, Tabs, Typography, message } from "antd";
import { CopyOutlined } from "@ant-design/icons";

interface CopyPreviewProps {
  copies: Record<string, string>;
}

export function CopyPreview({ copies }: CopyPreviewProps): JSX.Element {
  const platforms = Object.keys(copies);

  if (!platforms.length) {
    return <Typography.Text type="secondary">暂无文案</Typography.Text>;
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      message.success("已复制到剪贴板");
    });
  };

  return (
    <Tabs
      items={platforms.map((platform) => ({
        key: platform,
        label: platform,
        children: (
          <div>
            <Typography.Paragraph
              style={{ whiteSpace: "pre-wrap", background: "#fafafa", padding: 12, borderRadius: 8 }}
            >
              {copies[platform]}
            </Typography.Paragraph>
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={() => handleCopy(copies[platform])}
            >
              复制
            </Button>
          </div>
        ),
      }))}
    />
  );
}
