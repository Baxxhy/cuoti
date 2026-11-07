import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { navigate } from "@/lib/navigation";
import { ArrowUpRight, ChevronRight, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeading({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
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
    <div className="experience-link">
      <Sparkles size={16} />
      <span>教学经验支持</span>
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="查看参考教学案例"
        onClick={() => navigate("case-detail")}
      >
        <ArrowUpRight />
      </Button>
    </div>
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
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{description}</p>
      {children}
    </div>
  );
}
