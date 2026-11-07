import type { PageProps } from "@/App";
import {
  PageHeading,
  RouteButton,
  SectionHeading,
  Status,
  Surface,
} from "@/components/common";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useLearning } from "@/store";
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  FileCheck2,
  FileText,
  Layers,
  LoaderCircle,
  RotateCcw,
  Upload,
} from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

export function Manage({
  notify,
  course = false,
}: PageProps & { course?: boolean }) {
  const { casePublished, update } = useLearning();
  const [tab, setTab] = useState("case");
  const [source, setSource] = useState("");
  const [title, setTitle] = useState("从天平上的变化，走向等式的性质");
  const [content, setContent] = useState(
    "先请学生预测，再共同操作。用等式表达两边的变化，追问“同时”和“相同”的意义。学生只记住变号时，回到两边相同运算的完整过程。",
  );
  const [reviewed, setReviewed] = useState(false);
  const [fileName, setFileName] = useState("");
  const [preview, setPreview] = useState(false);
  return (
    <>
      <PageHeading
        title={
          course ? "把内容，组织成完整的一课。" : "让每一份经验，有据可查。"
        }
        description="对照原始材料整理教学经验，再核对、修订与发布。"
      >
        <Button variant="outline" onClick={() => setPreview(true)}>
          <BookOpen />
          查看案例预览
        </Button>
        <Button
          onClick={() => {
            if (!reviewed) return notify("请先勾选内容核对确认");
            update({ casePublished: true });
            notify("案例已模拟发布到教师案例库");
          }}
        >
          <Check />
          {casePublished ? "更新发布" : "核对并发布"}
        </Button>
      </PageHeading>
      <div className="content-workflow">
        <span className="workflow-step done">
          <FileText size={16} />
          材料整理
        </span>
        <ChevronRight size={14} />
        <span className="workflow-step current">
          <FileCheck2 size={16} />
          经验核对
        </span>
        <ChevronRight size={14} />
        <span
          className={casePublished ? "workflow-step done" : "workflow-step"}
        >
          <CheckCircle2 size={16} />
          发布应用
        </span>
        <Status>{casePublished ? "已模拟发布" : "待核对草稿"}</Status>
      </div>
      <div className="content-grid">
        <Surface className="source-material">
          <div className="section-heading">
            <h2>原始材料</h2>
            <Status tone="amber">自编示例</Status>
          </div>
          <label className="source-upload">
            <Upload size={17} />
            <span>{fileName || "选择资料文件"}</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,image/*"
              onChange={(event) =>
                setFileName(event.target.files?.[0]?.name || "")
              }
            />
          </label>
          <label className="field-label" htmlFor="source-link">
            公开资料出处
          </label>
          <Input
            id="source-link"
            value={source}
            onChange={(event) => setSource(event.target.value)}
            placeholder="整理真实材料时填写来源链接"
          />
          <div className="source-document">
            <div className="source-doc-label">
              <FileText size={15} />
              团队编写教学片段
            </div>
            <h3>从观察开始，理解共同变化。</h3>
            <p>
              展示相等的两边，让学生预测同时加入相同数量后，天平会怎样变化。先请学生解释，再通过操作验证。
            </p>
            <p className="highlighted-source">
              追问：如果只改变一边，会发生什么？请学生比较两种变化，并用自己的话说明相等关系。
            </p>
            <p>
              再引导学生将观察写为等式，讨论怎样通过两边的共同运算保持关系。
            </p>
            <div className="source-page-number">材料示例 · 第 1 页</div>
          </div>
          <p className="source-note">
            当前为团队编写材料，正式内容需登记真实作者、原文与使用条件。
          </p>
        </Surface>
        <Surface className="experience-editor">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="case">教学经验</TabsTrigger>
              <TabsTrigger value="lesson">课时关联</TabsTrigger>
            </TabsList>
          </Tabs>
          {tab === "case" ? (
            <>
              <label className="field-label" htmlFor="case-title">
                案例标题
              </label>
              <Input
                id="case-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
              <label className="field-label" htmlFor="experience-content">
                引导步骤与调整方式
              </label>
              <Textarea
                id="experience-content"
                value={content}
                onChange={(event) => setContent(event.target.value)}
                className="experience-textarea"
              />
              <div className="review-checks">
                <div>
                  <CheckCircle2 size={17} />
                  <span>示例数学关系</span>
                  <Status tone="green">人工核对</Status>
                </div>
                <div>
                  <CircleAlert size={17} />
                  <span>资料来源</span>
                  <Status tone="amber">待正式整理</Status>
                </div>
              </div>
              <label className="review-confirm">
                <input
                  type="checkbox"
                  checked={reviewed}
                  onChange={(event) => setReviewed(event.target.checked)}
                />
                我已核对当前自编示例的内容与标记
              </label>
              <div className="paper-actions">
                <Button
                  variant="outline"
                  onClick={() => {
                    sessionStorage.setItem(
                      "shicheng-case-draft",
                      JSON.stringify({ source, title, content }),
                    );
                    notify("当前案例草稿已保存到本次浏览会话");
                  }}
                >
                  保存草稿
                </Button>
                <Button
                  onClick={() => {
                    if (!reviewed) return notify("请先确认内容核对");
                    update({ casePublished: true });
                    notify("案例已模拟发布");
                  }}
                >
                  发布案例
                  <ArrowRight />
                </Button>
              </div>
            </>
          ) : (
            <div className="lesson-association">
              <Status tone="blue">七年级数学</Status>
              <h2>一元一次方程 / 等式性质</h2>
              <p>目标：解释两边共同变化的条件，并在新题中应用。</p>
              <div className="association-item">
                <Layers size={18} />
                <span>观察、解释、练习与独立检查</span>
              </div>
              <RouteButton route="courses" secondary>
                查看课程目录
              </RouteButton>
            </div>
          )}
        </Surface>
      </div>
      <Dialog open={preview} onOpenChange={setPreview}>
        <DialogContent className="case-preview-dialog">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>
              当前编辑内容预览 · 团队编写示例
            </DialogDescription>
          </DialogHeader>
          <div className="dialog-copy">{content}</div>
          <p className="source-note">
            来源：{source || "当前自编示例，待整理真实公开材料。"}
          </p>
        </DialogContent>
      </Dialog>
    </>
  );
}
export function Issues({ notify }: PageProps) {
  const [resolved, setResolved] = useState(false);
  const [reply, setReply] = useState(
    "我们会增加“只改变一边”的对比示例，帮助你观察相等关系。",
  );
  const [modal, setModal] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retried, setRetried] = useState(false);
  return (
    <>
      <PageHeading
        title="让问题，回到可以改进的地方。"
        description="定位具体内容，回复师生反馈，并继续未完成的任务。"
      />
      <Surface>
        <SectionHeading title="内容反馈" />
        <div className="feedback-issue">
          <span className="issue-icon">
            <CircleAlert size={21} />
          </span>
          <div>
            <h3>为什么只改变一边，等式就不成立了？</h3>
            <p>来自等式性质 · 观察活动 · 演示反馈</p>
          </div>
          <Status tone={resolved ? "green" : "amber"}>
            {resolved ? "已处理" : "待处理"}
          </Status>
          <Button variant="outline" onClick={() => setModal(true)}>
            {resolved ? "查看回复" : "处理反馈"}
            <ChevronRight />
          </Button>
        </div>
      </Surface>
      <Surface className="runtime-surface">
        <SectionHeading title="任务运行" />
        <div className="feedback-issue">
          <span className="issue-icon">
            <RotateCcw size={21} />
          </span>
          <div>
            <h3>配套教学内容生成</h3>
            <p>原型模拟任务 · 可重试并查看结果</p>
          </div>
          <Status tone={retried ? "green" : "amber"}>
            {retried ? "重试成功" : retrying ? "重试中" : "模拟失败"}
          </Status>
          <Button
            variant="outline"
            disabled={retrying || retried}
            onClick={() => {
              setRetrying(true);
              window.setTimeout(() => {
                setRetrying(false);
                setRetried(true);
                notify("演示任务重试完成");
              }, 900);
            }}
          >
            {retrying ? (
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
              >
                <LoaderCircle size={16} />
              </motion.span>
            ) : (
              <RotateCcw />
            )}
            {retried ? "已完成" : "重试任务"}
          </Button>
        </div>
      </Surface>
      <Dialog open={modal} onOpenChange={setModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>回复这次学习中的疑问</DialogTitle>
            <DialogDescription>等式性质 · 观察活动</DialogDescription>
          </DialogHeader>
          <Textarea
            value={reply}
            onChange={(event) => setReply(event.target.value)}
            aria-label="反馈回复"
          />
          <Button
            onClick={() => {
              setResolved(true);
              setModal(false);
              notify("反馈回复已在当前原型中记录");
            }}
          >
            确认处理
            <Check />
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
