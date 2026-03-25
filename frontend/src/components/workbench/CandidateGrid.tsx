import { Card, Checkbox, Empty, Image } from "antd";

import { getAssetUrl } from "../../lib/api";
import type { Candidate } from "../../lib/task-types";

interface CandidateGridProps {
  candidates: Candidate[];
  onSelect: (candidateId: number) => void;
  loading?: boolean;
}

export function CandidateGrid({ candidates, onSelect, loading }: CandidateGridProps): JSX.Element {
  if (!candidates.length) {
    return <Empty description="暂无候选图片" />;
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
      {candidates.map((c) => (
        <Card
          key={c.id}
          hoverable
          size="small"
          onClick={() => onSelect(c.id)}
          style={{
            border: c.is_selected ? "2px solid #0f3d3e" : "1px solid #d9d9d9",
            position: "relative",
          }}
          cover={
            <Image
              src={getAssetUrl(c.file_path)}
              alt={`候选 ${c.id}`}
              preview={false}
              style={{ height: 140, objectFit: "cover" }}
            />
          }
        >
          <Checkbox checked={c.is_selected} style={{ position: "absolute", top: 8, right: 8 }} />
          <Card.Meta description={c.source_type} />
        </Card>
      ))}
    </div>
  );
}
