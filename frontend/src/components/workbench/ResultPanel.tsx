import { Card, Empty, Image, Typography } from "antd";

import { getAssetUrl } from "../../lib/api";
import type { Candidate } from "../../lib/task-types";
import type { Asset, Version } from "../../lib/types";

interface ResultPanelProps {
  candidates: Candidate[];
  sceneVersions?: Version[];
  activeVersion?: Version | null;
}

function getPreviewAsset(version: Version): Asset | undefined {
  return (
    version.assets.find((a) => a.asset_type === "final_export") ??
    version.assets.find((a) => a.asset_type === "composite") ??
    version.assets[0]
  );
}

export function ResultPanel({ candidates, sceneVersions, activeVersion }: ResultPanelProps): JSX.Element {
  // Show active version preview if available
  if (activeVersion) {
    const asset = getPreviewAsset(activeVersion);
    return (
      <Card title={`版本 v${activeVersion.version_no}`} size="small">
        {asset ? (
          <Image src={getAssetUrl(asset.file_path)} alt="预览" style={{ maxWidth: "100%" }} />
        ) : (
          <Empty description="暂无预览" />
        )}
        {activeVersion.title_text && (
          <Typography.Paragraph style={{ marginTop: 8 }}>{activeVersion.title_text}</Typography.Paragraph>
        )}
      </Card>
    );
  }

  // Show scene versions grid
  if (sceneVersions && sceneVersions.length > 0) {
    return (
      <div>
        <Typography.Text strong style={{ marginBottom: 8, display: "block" }}>场景图</Typography.Text>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
          {sceneVersions.map((v) => {
            const asset = getPreviewAsset(v);
            return (
              <Card key={v.id} size="small" hoverable>
                {asset && <Image src={getAssetUrl(asset.file_path)} alt={`场景 ${v.version_no}`} preview style={{ width: "100%" }} />}
              </Card>
            );
          })}
        </div>
      </div>
    );
  }

  // Show selected candidate
  const selected = candidates.find((c) => c.is_selected);
  if (selected) {
    return (
      <Card title="已选参考图" size="small">
        <Image src={getAssetUrl(selected.file_path)} alt="参考图" style={{ maxWidth: "100%" }} />
      </Card>
    );
  }

  return <Empty description="等待输入" />;
}
