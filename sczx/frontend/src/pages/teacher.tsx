import type { PageProps } from "@/App";
import {
  EmptyState,
  PageHeading,
  RouteButton,
  SectionHeading,
  Status,
  Surface,
} from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Workspace } from "@/components/workspace";
import { navigate } from "@/lib/navigation";
import {
  demoStudents,
  initialBlocks,
  useLearning,
  type LessonBlock,
} from "@/store";
import { DragDropProvider } from "@dnd-kit/react";
import { isSortable, useSortable } from "@dnd-kit/react/sortable";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  Eye,
  FileText,
  GripVertical,
  LibraryBig,
  Plus,
  Save,
  Search,
  Send,
  Sparkles,
  Star,
  Users,
  WandSparkles,
} from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

export function Cases() {
  const { favorite } = useLearning();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("all");
  const matches =
    !query ||
    ["等式", "天平", "同时", "变号", "学生", "困难", "相同"].some((word) =>
      query.includes(word),
    );
  return (
    <>
      <PageHeading
        title="好教法，值得被更多人看见。"
        description="从具体的学生困难出发，寻找适合下一堂课的教学经验。"
      />
      <div className="case-toolbar">
        <div className="search-field">
          <Search size={17} />
          <Input
            aria-label="搜索教学案例"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索知识点、目标或学生困难"
          />
        </div>
        <Select defaultValue="math" items={{ math: "七年级数学" }}>
          <SelectTrigger aria-label="选择学科年级">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="math">七年级数学</SelectItem>
          </SelectContent>
        </Select>
        <Select defaultValue="equation" items={{ equation: "一元一次方程" }}>
          <SelectTrigger aria-label="选择单元">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="equation">一元一次方程</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="all">全部案例</TabsTrigger>
          <TabsTrigger value="favorite">我的收藏</TabsTrigger>
        </TabsList>
      </Tabs>
      {matches && (tab === "all" || favorite) ? (
        <div className="case-grid">
          <motion.article className="featured-case" whileHover={{ y: -3 }}>
            <div className="case-image">
              <img
                src="/images/equation-balance.png"
                alt="天平与等式教学案例封面"
              />
              <Badge variant="secondary">等式性质</Badge>
            </div>
            <div className="featured-case-body">
              <div className="case-meta">
                <BookOpen size={14} />
                <span>团队编写案例示例</span>
                <span>·</span>
                <span>观察与追问</span>
              </div>
              <h2>
                从天平上的变化，
                <br />
                走向等式的性质。
              </h2>
              <p>
                当学生会说“移过去变号”，却说不清为什么时，让观察、操作与解释重新连接起来。
              </p>
              <div className="case-footer">
                <span>
                  <Users size={14} />
                  适用初学等式性质的学生
                </span>
                <Button onClick={() => navigate("case-detail")}>
                  阅读案例
                  <ArrowUpRight />
                </Button>
              </div>
            </div>
          </motion.article>
          <aside className="case-reading-guide">
            <span className="guide-mark">
              <LibraryBig size={27} strokeWidth={1.4} />
            </span>
            <h2>
              找到方法之前，
              <br />
              先找到学生的困难。
            </h2>
            <p>
              案例记录怎样引入、怎样提问，以及学生没有理解时，怎样调整讲法。
            </p>
            <div className="case-question-links">
              {[
                "学生只改变等式的一边",
                "学生机械记忆移项变号",
                "怎样检查学生独立理解",
              ].map((text) => (
                <button key={text} onClick={() => setQuery(text)}>
                  {text}
                  <ArrowUpRight size={15} />
                </button>
              ))}
            </div>
            <p className="source-note">
              公开来源与使用条件将在内容整理阶段逐项核对。当前为完整流程的自编示例。
            </p>
          </aside>
        </div>
      ) : (
        <Surface>
          <EmptyState
            title="暂时没有匹配的案例"
            description={
              tab === "favorite"
                ? "阅读案例后，可以点击收藏。"
                : "试试“等式”“天平”或“变号”。"
            }
          >
            <Button
              variant="outline"
              onClick={() => {
                setQuery("");
                setTab("all");
              }}
            >
              浏览全部案例
            </Button>
          </EmptyState>
        </Surface>
      )}
    </>
  );
}
export function CaseDetail({ notify }: PageProps) {
  const { favorite, update } = useLearning();
  return (
    <>
      <div className="back-line">
        <Button variant="ghost" onClick={() => navigate("cases")}>
          <ArrowLeft />
          返回教学案例
        </Button>
      </div>
      <div className="case-detail-header">
        <div>
          <Status tone="blue">等式性质 · 案例示例</Status>
          <h1>
            从天平上的变化，
            <br />
            走向等式的性质。
          </h1>
          <p>把“知道怎么做”，带向“能够说清为什么”。</p>
        </div>
        <div className="heading-actions">
          <Button
            variant="outline"
            onClick={() => {
              update({ favorite: !favorite });
              notify(favorite ? "已取消收藏" : "案例已加入收藏");
            }}
          >
            <Star fill={favorite ? "currentColor" : "none"} />
            {favorite ? "已收藏" : "收藏案例"}
          </Button>
          <RouteButton route="prepare">用于备课</RouteButton>
        </div>
      </div>
      <div className="case-detail-grid">
        <article className="case-article">
          <div className="case-article-section">
            <span className="article-marker">
              <Eye size={19} />
            </span>
            <div>
              <h2>先请学生预测，再让操作发生。</h2>
              <p>
                展示两边相等的天平，请学生预测两边同时加入相同数量的砝码后，平衡会不会改变。让学生先表达自己的理由，再动手验证。
              </p>
              <blockquote>
                “如果只在左边加一个，它还会平衡吗？你为什么这样想？”
              </blockquote>
            </div>
          </div>
          <div className="case-article-section">
            <span className="article-marker">
              <FileText size={19} />
            </span>
            <div>
              <h2>把观察，变成可以解释的等式。</h2>
              <p>
                记录两边共同变化的完整步骤，让学生说出“同时”和“相同”分别意味着什么。再用只改变一边的例子进行对照。
              </p>
              <div className="article-equation">
                a = b <span>⇒</span> a + c = b + c
              </div>
            </div>
          </div>
          <div className="case-article-section">
            <span className="article-marker">
              <Sparkles size={19} />
            </span>
            <div>
              <h2>依据回应，决定下一步怎么讲。</h2>
              <p>
                当学生只说“移项变号”时，请其写出两边同时减去同一个数的过程。学生能够解释后，再改变数字给出新题，观察能否独立完成。
              </p>
            </div>
          </div>
        </article>
        <aside>
          <Surface className="case-use-card">
            <h3>这篇案例适合什么时候？</h3>
            <div>
              <span>学习基础</span>
              <p>理解相等关系，掌握加减法</p>
            </div>
            <div>
              <span>常见困难</span>
              <p>只改变一边，机械记忆变号</p>
            </div>
            <div>
              <span>教学目标</span>
              <p>解释共同变化，独立应用等式性质</p>
            </div>
            <div className="source-box">
              <BookOpen size={16} />
              <p>
                团队编写示例
                <br />
                <small>公开原文将在内容建设阶段补充。</small>
              </p>
            </div>
            <RouteButton route="prepare">带入我的教案</RouteButton>
          </Surface>
        </aside>
      </div>
    </>
  );
}
function SortableBlock({
  block,
  index,
  onGenerate,
  busy,
}: {
  block: LessonBlock;
  index: number;
  onGenerate: (id: string) => void;
  busy: boolean;
}) {
  const { ref, handleRef, isDragging } = useSortable({
    id: block.id,
    index,
    transition: null,
  });
  const updateBlock = useLearning((state) => state.updateBlock);
  return (
    <div ref={ref} className={`editor-block ${isDragging ? "dragging" : ""}`}>
      <div className="editor-block-heading">
        <button
          ref={handleRef}
          className="drag-handle"
          aria-label={`拖动排序：${block.title}`}
        >
          <GripVertical size={16} />
        </button>
        <h3>{block.title}</h3>
        <Button
          size="icon-xs"
          variant="ghost"
          aria-label={`重新生成${block.title}`}
          disabled={busy}
          onClick={() => onGenerate(block.id)}
        >
          <WandSparkles />
        </Button>
      </div>
      <Textarea
        aria-label={block.title}
        value={block.content}
        onChange={(event) => updateBlock(block.id, event.target.value)}
        disabled={busy}
      />
      <div className="block-footnote">
        <span>{busy ? "正在模拟生成……" : "对应学生学习活动"}</span>
        <span>活动 {index + 1}</span>
      </div>
    </div>
  );
}
export function Prepare({ notify }: PageProps) {
  const {
    blocks,
    reorder,
    updateBlock,
    update,
    published,
    lessonGoal: goal,
    studentBase,
    dueDate,
  } = useLearning();
  const [modal, setModal] = useState<"preview" | "publish" | null>(null);
  const [busyBlock, setBusyBlock] = useState("");
  const [previewTab, setPreviewTab] = useState("student");
  function regenerate(id: string) {
    setBusyBlock(id);
    window.setTimeout(() => {
      const initial = initialBlocks.find((block) => block.id === id)!;
      updateBlock(
        id,
        `${initial.content} 请学生先表达自己的预测，再用一个具体例子说明理由。`,
      );
      setBusyBlock("");
      notify("演示教学建议已生成，可以继续修改");
    }, 700);
  }
  const preview = (
    <div className="student-preview">
      <div className="preview-top">
        <span className="preview-avatar">
          <GraduationSymbol />
        </span>
        <span>学生会看到的内容</span>
        <Badge variant="secondary">预览</Badge>
      </div>
      <div className="preview-course-cover">
        <img src="/images/equation-balance.png" alt="学生课时封面" />
        <div>
          <span>第一课</span>
          <h3>等式性质</h3>
        </div>
      </div>
      <div className="preview-lesson-body">
        <span className="tiny-label">这节课，我们将学会</span>
        <p className="preview-goal">{goal}</p>
        {blocks.map((block, index) => (
          <div className="preview-activity" key={block.id}>
            <span>{index + 1}</span>
            <div>
              <h4>{block.title}</h4>
              <p>{block.content}</p>
            </div>
          </div>
        ))}
        <div className="article-equation">a = b ⇒ a + c = b + c</div>
      </div>
    </div>
  );
  const editor = (
    <div className="lesson-editor">
      <div className="editor-intro">
        <span>
          <FileText size={16} />
          教师教学安排
        </span>
        <Status>自动保存到本地</Status>
      </div>
      <label className="field-label" htmlFor="lesson-goal">
        本课目标
      </label>
      <Input
        id="lesson-goal"
        value={goal}
        onChange={(event) => update({ lessonGoal: event.target.value })}
      />
      <label className="field-label" htmlFor="student-base">
        学生基础
      </label>
      <Input
        id="student-base"
        value={studentBase}
        onChange={(event) => update({ studentBase: event.target.value })}
      />
      <div className="editor-section-heading">
        <h2>教学活动</h2>
        <span>
          <GripVertical size={13} />
          拖动手柄调整顺序
        </span>
      </div>
      <DragDropProvider
        onDragEnd={(event) => {
          if (event.canceled) return;
          const source = event.operation.source;
          if (isSortable(source) && source.initialIndex !== source.index) {
            reorder(source.initialIndex, source.index);
            notify("教学活动与学生预览已同步排序");
          }
        }}
      >
        <div className="sortable-list">
          {blocks.map((block, index) => (
            <SortableBlock
              block={block}
              index={index}
              key={block.id}
              busy={busyBlock === block.id}
              onGenerate={regenerate}
            />
          ))}
        </div>
      </DragDropProvider>
      <button
        className="reference-link"
        onClick={() => navigate("case-detail")}
      >
        <LibraryBig size={16} />
        <span>参考案例 · 从天平上的变化，走向等式的性质</span>
        <ArrowUpRight size={15} />
      </button>
    </div>
  );
  return (
    <>
      <div className="back-line">
        <Button variant="ghost" onClick={() => navigate("teacher")}>
          <ArrowLeft />
          返回教学概览
        </Button>
        <span>我的教案 / 等式性质</span>
      </div>
      <PageHeading
        title="把好经验，备成自己的一堂课。"
        description="等式性质 · 教师安排与学生内容配套编辑。"
      >
        <Button
          variant="outline"
          onClick={() => {
            notify("教案内容已保存到本地浏览器");
          }}
        >
          <Save />
          保存教案
        </Button>
        <Button variant="outline" onClick={() => setModal("preview")}>
          <Eye />
          学生预览
        </Button>
        <Button onClick={() => setModal("publish")}>
          <Send />
          {published ? "再次发布" : "发布任务"}
        </Button>
      </PageHeading>
      <Workspace
        primary={editor}
        secondary={
          <>
            <div className="preview-pane-tabs">
              <Tabs value={previewTab} onValueChange={setPreviewTab}>
                <TabsList>
                  <TabsTrigger value="student">学生内容</TabsTrigger>
                  <TabsTrigger value="source">参考经验</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            {previewTab === "student" ? (
              preview
            ) : (
              <div className="preview-source">
                <BookOpen size={28} />
                <h2>从天平上的变化，走向等式的性质</h2>
                <p>
                  先预测，再操作，最后解释。根据学生回应调整讲法，将“同时”和“相同”落实到每一步。
                </p>
                <RouteButton route="case-detail" secondary>
                  阅读完整案例
                </RouteButton>
              </div>
            )}
          </>
        }
      />
      <Dialog
        open={modal !== null}
        onOpenChange={(open) => !open && setModal(null)}
      >
        <DialogContent
          className={
            modal === "preview" ? "lesson-preview-dialog" : "publish-dialog"
          }
        >
          <DialogHeader>
            <DialogTitle>
              {modal === "preview"
                ? "以学生的视角，看一看这堂课"
                : "让这堂课，与学生相遇"}
            </DialogTitle>
            <DialogDescription>
              {modal === "preview"
                ? "预览顺序与当前教案保持一致。"
                : "确认班级与时间，发布配套的课时内容。"}
            </DialogDescription>
          </DialogHeader>
          {modal === "preview" ? (
            <>
              {preview}
              <Button onClick={() => setModal("publish")}>
                继续发布
                <ArrowRight />
              </Button>
            </>
          ) : (
            <>
              <div className="publish-course">
                <FileText size={22} />
                <div>
                  <strong>等式性质</strong>
                  <small>{blocks.length} 个教学活动 · 配套学生内容</small>
                </div>
              </div>
              <label className="field-label">发布班级</label>
              <Select
                defaultValue="demo"
                items={{ demo: "七年级一班 · 演示班级" }}
              >
                <SelectTrigger className="w-full" aria-label="选择发布班级">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="demo">七年级一班 · 演示班级</SelectItem>
                </SelectContent>
              </Select>
              <label className="field-label" htmlFor="due-date">
                建议完成日期
              </label>
              <Input
                id="due-date"
                type="date"
                value={dueDate}
                onChange={(event) => update({ dueDate: event.target.value })}
              />
              <p className="small-caption">
                本次为模拟发布，学生空间与班级任务将同步显示状态。
              </p>
              <Button
                onClick={() => {
                  update({ published: true });
                  setModal(null);
                  navigate("class");
                  notify("课时已模拟发布给七年级一班");
                }}
              >
                确认发布
                <ArrowRight />
              </Button>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
function GraduationSymbol() {
  return <BookOpen size={17} />;
}
export function Classroom({ notify }: PageProps) {
  const { published } = useLearning();
  const [invite, setInvite] = useState(false);
  return (
    <>
      <PageHeading
        title="七年级一班"
        description="每一次教学与学习，都在这里连接。"
      >
        <Button variant="outline" onClick={() => setInvite(true)}>
          <Users />
          邀请学生
        </Button>
        <RouteButton route="prepare">发布新任务</RouteButton>
      </PageHeading>
      <div className="class-banner">
        <div className="class-mark">
          <Users size={35} strokeWidth={1.4} />
        </div>
        <div>
          <h2>一起学习，也看见每一个人。</h2>
          <p>3 名演示学生 · 数学 · 一元一次方程</p>
        </div>
        <div className="student-avatars">
          {demoStudents.map((student) => (
            <span key={student.name}>{student.initials}</span>
          ))}
        </div>
      </div>
      <SectionHeading title="班级学习任务" />
      <Surface>
        <div className="class-task">
          <span className="task-icon blue">
            <FileText size={23} />
          </span>
          <div>
            <h3>等式性质 · 观察、解释与应用</h3>
            <p>课时学习、互动活动、独立检查与错题补救</p>
            <div className="class-task-meta">
              <Status tone={published ? "green" : "neutral"}>
                {published ? "已模拟发布" : "示例任务"}
              </Status>
              <span>1 / 3 名演示学生已提交</span>
            </div>
          </div>
          <RouteButton route="insights">查看作答与反馈</RouteButton>
        </div>
      </Surface>
      <Dialog open={invite} onOpenChange={setInvite}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>邀请学生加入班级</DialogTitle>
            <DialogDescription>七年级一班 · 演示邀请</DialogDescription>
          </DialogHeader>
          <div className="invitation-code">SCZX DEMO</div>
          <p className="small-caption">
            此口令用于界面演示，正式邀请在业务开发阶段接入。
          </p>
          <Button
            onClick={async () => {
              try {
                await navigator.clipboard.writeText("SCZX-DEMO");
                notify("演示口令已复制");
              } catch {
                notify("请手动复制口令 SCZX-DEMO");
              }
            }}
          >
            复制口令
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
export function Insights({ notify }: PageProps) {
  const { feedback, update } = useLearning();
  const [draft, setDraft] = useState(feedback);
  const [student, setStudent] = useState<number | null>(null);
  const [supplement, setSupplement] = useState(false);
  const submitted = demoStudents.filter(
    (item) => item.status === "已提交",
  ).length;
  return (
    <>
      <div className="back-line">
        <Button variant="ghost" onClick={() => navigate("class")}>
          <ArrowLeft />
          七年级一班
        </Button>
        <span>等式性质 / 学情反馈</span>
      </div>
      <PageHeading
        title="看见答案，更看见思考。"
        description="把原作答、获得的帮助与独立检查放在一起看。"
      >
        <Button onClick={() => setSupplement(true)}>
          <Plus />
          安排补充学习
        </Button>
      </PageHeading>
      <div className="insight-summary">
        <div>
          <span>参与学生</span>
          <strong>
            {demoStudents.length}
            <small>人</small>
          </strong>
        </div>
        <div>
          <span>已经提交</span>
          <strong>
            {submitted}
            <small>/ {demoStudents.length}</small>
          </strong>
        </div>
        <div>
          <span>新题独立完成</span>
          <strong>
            {
              demoStudents.filter((item) => item.result === "新题独立完成")
                .length
            }
            <small>人</small>
          </strong>
        </div>
        <div className="summary-context">
          <Status>演示学情</Status>
          <p>结果来自下方示例学生记录</p>
        </div>
      </div>
      <Surface className="student-table">
        <SectionHeading title="学生学习过程" />
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th>学习进度</th>
                <th>获得的帮助</th>
                <th>独立检查</th>
                <th>
                  <span className="sr-only">操作</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {demoStudents.map((item, index) => (
                <tr key={item.name}>
                  <td>
                    <span className={`student-name avatar-${index}`}>
                      <span>{item.initials}</span>
                      {item.name}
                    </span>
                  </td>
                  <td>
                    <div className="table-progress">
                      <span>{item.status}</span>
                      <Progress
                        value={item.progress}
                        aria-label={`${item.name}学习进度`}
                      />
                    </div>
                  </td>
                  <td>{item.help}</td>
                  <td>
                    <Status
                      tone={
                        item.result === "新题独立完成" ? "green" : "neutral"
                      }
                    >
                      {item.result}
                    </Status>
                  </td>
                  <td>
                    <Button variant="ghost" onClick={() => setStudent(index)}>
                      查看过程
                      <ArrowUpRight />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Surface>
      <div className="two-column insight-detail">
        <Surface className="common-difficulty">
          <div className="section-heading">
            <h2>值得关注的共同困难</h2>
            <Sparkles size={17} />
          </div>
          <h3>会说“变号”，却还没说清为什么。</h3>
          <p>
            在示例作答中，学生消去了等式左边的数，却没有对右边进行相同运算。可以回到完整步骤，再安排新题。
          </p>
          <RouteButton route="cases" secondary>
            查找相关教学经验
          </RouteButton>
        </Surface>
        <Surface>
          <SectionHeading title="给学生的反馈" />
          <Textarea
            aria-label="教师反馈"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="paper-actions">
            <Button
              onClick={() => {
                update({ feedback: draft });
                notify("反馈已保存，学生可以在本课结果中查看");
              }}
            >
              <Check />
              确认并保存
            </Button>
          </div>
        </Surface>
      </div>
      <Dialog
        open={student !== null}
        onOpenChange={(open) => !open && setStudent(null)}
      >
        <DialogContent className="student-detail-dialog">
          <DialogHeader>
            <DialogTitle>
              {student !== null && demoStudents[student].name}的学习过程
            </DialogTitle>
            <DialogDescription>等式性质 · 演示作答与帮助记录</DialogDescription>
          </DialogHeader>
          {student === 0 ? (
            <div className="attempt-timeline">
              <div>
                <span className="timeline-dot" />
                <small>最初的作答</small>
                <div className="math-equation">x + 3 = 8 → x = 8 + 3</div>
              </div>
              <div>
                <span className="timeline-dot" />
                <small>获得提示</small>
                <p>试着在等式两边同时减去 3。</p>
              </div>
              <div>
                <span className="timeline-dot green" />
                <small>新题独立应用</small>
                <p>y + 4 = 11，回答 y = 7。</p>
                <Status tone="green">独立完成</Status>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <h3>{student !== null && demoStudents[student].status}</h3>
              <p>
                {student !== null && demoStudents[student].help}
                ，后续作答在完成后展示。
              </p>
            </div>
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={supplement} onOpenChange={setSupplement}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>把下一步指导，送到学生身边</DialogTitle>
            <DialogDescription>为七年级一班安排补充学习。</DialogDescription>
          </DialogHeader>
          <label className="field-label" htmlFor="supplement-content">
            补充内容
          </label>
          <Textarea
            id="supplement-content"
            defaultValue="回到等式两边同时减去相同数的完整过程，再完成一道独立检查题。"
          />
          <Button
            onClick={() => {
              setSupplement(false);
              notify("已模拟安排补充学习");
            }}
          >
            确认安排
            <Send />
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
