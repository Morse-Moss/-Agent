import { Steps } from "antd";

import type { TaskStep } from "../../lib/task-types";
import { STEP_LABELS } from "../../lib/task-types";

const ORDERED_STEPS: TaskStep[] = [
  "input",
  "product_select",
  "scene_generate",
  "content_extend",
  "review_finalize",
];

interface StepBarProps {
  currentStep: TaskStep;
  onStepClick?: (step: TaskStep) => void;
}

export function StepBar({ currentStep, onStepClick }: StepBarProps): JSX.Element {
  const currentIndex = ORDERED_STEPS.indexOf(currentStep);

  return (
    <Steps
      current={currentIndex}
      size="small"
      style={{ marginBottom: 24 }}
      items={ORDERED_STEPS.map((step, idx) => ({
        title: STEP_LABELS[step],
        status: idx < currentIndex ? "finish" : idx === currentIndex ? "process" : "wait",
        onClick: onStepClick ? () => onStepClick(step) : undefined,
        style: onStepClick ? { cursor: "pointer" } : undefined,
      }))}
    />
  );
}
