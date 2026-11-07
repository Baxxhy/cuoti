import { GripVertical } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";

export function Workspace({
  primary,
  secondary,
}: {
  primary: ReactNode;
  secondary: ReactNode;
}) {
  const [compact, setCompact] = useState(
    window.matchMedia("(max-width: 1000px)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(max-width: 1000px)");
    const update = () => setCompact(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  if (compact)
    return (
      <div className="workspace-stacked">
        <div>{primary}</div>
        <div>{secondary}</div>
      </div>
    );
  return (
    <Group
      orientation="horizontal"
      className="workspace-panels"
      id="learning-workspace"
    >
      <Panel defaultSize="64%" minSize="42%">
        <div className="panel-scroll">{primary}</div>
      </Panel>
      <Separator
        className="resize-handle"
        aria-label="调整主内容与参考面板宽度"
      >
        <GripVertical size={13} />
      </Separator>
      <Panel defaultSize="36%" minSize="28%">
        <div className="panel-scroll secondary-pane">{secondary}</div>
      </Panel>
    </Group>
  );
}
