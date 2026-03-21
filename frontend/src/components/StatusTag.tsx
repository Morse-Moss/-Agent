import { Tag } from "antd";

import type { ProjectStatus, ReviewStatus } from "../lib/types";

type StatusValue = ProjectStatus | ReviewStatus;

const statusMap: Record<StatusValue, { color: string; label: string }> = {
  unreviewed: { color: "gold", label: "未审核" },
  approved: { color: "green", label: "已通过" },
  rejected: { color: "red", label: "已驳回" },
  finalized: { color: "blue", label: "已定稿" },
};

export function StatusTag({ status }: { status: StatusValue }): JSX.Element {
  const meta = statusMap[status];
  return <Tag color={meta.color}>{meta.label}</Tag>;
}
