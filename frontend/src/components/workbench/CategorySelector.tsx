import { Empty, TreeSelect } from "antd";
import { useMemo } from "react";

import type { ProductCategory } from "../../lib/task-types";

interface CategorySelectorProps {
  categories: ProductCategory[];
  value?: number;
  onChange: (categoryId: number) => void;
  loading?: boolean;
}

function buildTreeData(categories: ProductCategory[]): { title: string; value: number; children?: ReturnType<typeof buildTreeData> }[] {
  // Build a map of parent_id -> children
  const roots = categories.filter((c) => c.parent_id === null);
  const childMap = new Map<number, ProductCategory[]>();
  for (const cat of categories) {
    if (cat.parent_id !== null) {
      const siblings = childMap.get(cat.parent_id) ?? [];
      siblings.push(cat);
      childMap.set(cat.parent_id, siblings);
    }
  }

  function toNode(cat: ProductCategory): { title: string; value: number; children?: ReturnType<typeof buildTreeData> } {
    const kids = childMap.get(cat.id);
    return {
      title: cat.name,
      value: cat.id,
      children: kids?.map(toNode),
    };
  }

  return roots.map(toNode);
}

export function CategorySelector({ categories, value, onChange, loading }: CategorySelectorProps): JSX.Element {
  const treeData = useMemo(() => buildTreeData(categories), [categories]);

  if (!categories.length && !loading) {
    return <Empty description="暂无产品类目" />;
  }

  return (
    <TreeSelect
      treeData={treeData}
      value={value}
      onChange={onChange}
      placeholder="选择产品类目"
      style={{ width: "100%" }}
      loading={loading}
      treeDefaultExpandAll
    />
  );
}
