import { Tabs } from "antd";

import type { EntryType } from "../../lib/task-types";
import { ENTRY_LABELS } from "../../lib/task-types";

interface EntryTabsProps {
  activeEntry: EntryType;
  onChange: (entry: EntryType) => void;
  disabled?: boolean;
}

const ENTRIES: EntryType[] = ["competitor_link", "white_bg_upload", "image_scene_video"];

export function EntryTabs({ activeEntry, onChange, disabled }: EntryTabsProps): JSX.Element {
  return (
    <Tabs
      activeKey={activeEntry}
      onChange={(key) => onChange(key as EntryType)}
      items={ENTRIES.map((entry) => ({
        key: entry,
        label: ENTRY_LABELS[entry],
        disabled,
      }))}
      style={{ marginBottom: 16 }}
    />
  );
}
