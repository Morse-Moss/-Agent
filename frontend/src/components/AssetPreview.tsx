import { Card, Image, Space, Tag, Typography } from "antd";

import { getAssetUrl } from "../lib/api";
import type { Asset } from "../lib/types";

const assetTypeLabelMap: Record<string, string> = {
  source: "源图",
  cutout: "抠图结果",
  background: "背景图",
  composite: "合成图",
  final_export: "最终导出图",
};

export function AssetPreview({ assets }: { assets: Asset[] }): JSX.Element {
  const finalAsset = assets.find((asset) => asset.asset_type === "final_export") ?? assets[assets.length - 1];

  if (!finalAsset) {
    return (
      <Card size="small" className="asset-card">
        <Typography.Text type="secondary">当前版本还没有可预览图片。</Typography.Text>
      </Card>
    );
  }

  return (
    <Card
      size="small"
      cover={<Image alt={assetTypeLabelMap[finalAsset.asset_type] ?? finalAsset.asset_type} src={getAssetUrl(finalAsset.file_path)} preview />}
      className="asset-card"
    >
      <Space wrap>
        {assets.map((asset) => (
          <Tag key={asset.id}>{assetTypeLabelMap[asset.asset_type] ?? asset.asset_type}</Tag>
        ))}
      </Space>
    </Card>
  );
}
