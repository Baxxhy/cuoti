import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card,CardContent } from "@/components/ui/card";
import {
Tooltip,
TooltipContent,
TooltipTrigger,
} from "@/components/ui/tooltip";
import { navigate } from "@/lib/navigation";
import { BookOpen,ChevronRight,Info } from "lucide-react";
import { useId, type ReactNode } from "react";

export function PageHeading({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
export function SectionHeading({
  title,
  action,
  route,
}: {
  title: string;
  action?: string;
  route?: string;
}) {
  return (
    <div className="section-heading">
      <h2>{title}</h2>
      {action && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => route && navigate(route)}
        >
          {action}
          <ChevronRight />
        </Button>
      )}
    </div>
  );
}
export function Surface({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={`surface ${className}`}>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
export function RouteButton({
  route,
  children,
  secondary = false,
}: {
  route: string;
  children: ReactNode;
  secondary?: boolean;
}) {
  return (
    <Button
      variant={secondary ? "outline" : "default"}
      onClick={() => navigate(route)}
    >
      {children}
      <ChevronRight data-icon="inline-end" />
    </Button>
  );
}
export function ExperienceLink() {
  return (
    <Button
      variant="ghost"
      className="experience-link"
      onClick={() => navigate("case-detail")}
    >
      <BookOpen size={15} />
      参考案例
      <ChevronRight size={14} />
    </Button>
  );
}
export function InfoTip({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const descriptionId = useId();
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            className="info-tip"
            aria-label={label}
            aria-describedby={descriptionId}
          />
        }
      >
        <Info size={15} />
      </TooltipTrigger>
      <TooltipContent id={descriptionId} role="tooltip" className="max-w-72 text-xs leading-relaxed">
        {children}
      </TooltipContent>
    </Tooltip>
  );
}
export function Status({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "amber" | "blue";
}) {
  return (
    <Badge variant="secondary" className={`status-badge tone-${tone}`}>
      {children}
    </Badge>
  );
}
export function EmptyState({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {children}
    </div>
  );
}
