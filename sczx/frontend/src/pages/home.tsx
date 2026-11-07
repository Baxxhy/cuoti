import {
  EmptyState,
  PageHeading,
  RouteButton,
  SectionHeading,
  Status,
  Surface,
} from "@/components/common";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { navigate } from "@/lib/navigation";
import { useLearning } from "@/store";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Calculator,
  ChevronRight,
  CircleCheck,
  Clock3,
  FileText,
  Lightbulb,
  Sparkles,
  Target,
} from "lucide-react";
import { motion } from "motion/react";

export function Home({ teacher = false }: { teacher?: boolean }) {
  const { published, completed, attempts } = useLearning();
  return (
    <>
      <PageHeading
        title={
          teacher ? "让好经验，成为你的下一堂课。" : "今天，也向理解多走一步。"
        }
        description={
          teacher
            ? "从案例里发现灵感，在课堂上看见每一个学生。"
            : "从一个好问题开始，把学过的知识变成自己的理解。"
        }
      >
        <span className="date-label">11 月 7 日，星期六</span>
      </PageHeading>
      <div className="home-grid">
        <div className="home-main">
          <motion.section className="lesson-hero" whileHover={{ y: -2 }}>
            <img
              src="/images/equation-balance.png"
              alt="保持平衡的金色天平，两侧分别放着白色砝码和紫色方块"
              fetchPriority="high"
            />
            <div className="hero-copy">
              <span className="hero-category">
                <BookOpen size={14} />
                七年级数学 · 第一单元
              </span>
              <h2>
                {teacher ? (
                  <>
                    从一架天平，
                    <br />
                    设计一堂好课。
                  </>
                ) : (
                  <>
                    两边一起变化，
                    <br />
                    相等为何不变？
                  </>
                )}
              </h2>
              <p>
                等式性质<span>·</span>
                {teacher ? "教案与学生内容配套设计" : "从观察中发现数学的道理"}
              </p>
              <Button
                onClick={() => navigate(teacher ? "prepare" : "learn")}
                size="lg"
              >
                {teacher ? "继续备课" : completed ? "回看本课" : "继续学习"}
                <ArrowRight size={16} />
              </Button>
              <div className="hero-progress">
                <Progress
                  value={completed ? 100 : 40}
                  aria-label="当前课时进度"
                />
                <small>
                  {teacher
                    ? "草稿已保存，继续完善教学活动"
                    : completed
                      ? "本课学习结果已提交"
                      : "已完成 2 个活动，共 5 个"}
                </small>
              </div>
            </div>
          </motion.section>
          <section className="task-section">
            <SectionHeading
              title={teacher ? "班级教学" : "我的学习任务"}
              action="查看全部"
              route={teacher ? "class" : "courses"}
            />
            <div className="task-row">
              <span className="task-icon blue">
                <FileText size={20} />
              </span>
              <div className="task-description">
                <h3>等式性质 · 观察、解释与应用</h3>
                <p>
                  七年级一班<span>·</span>
                  {published ? "教师已发布" : "演示学习任务"}
                </p>
              </div>
              <Status tone={completed ? "green" : "blue"}>
                {completed ? "已提交" : "学习中"}
              </Status>
              <Button
                size="icon"
                variant="ghost"
                aria-label="打开等式性质任务"
                onClick={() => navigate(teacher ? "insights" : "learn")}
              >
                <ArrowUpRight />
              </Button>
            </div>
            <div className="task-row">
              <span className="task-icon amber">
                <Lightbulb size={20} />
              </span>
              <div className="task-description">
                <h3>
                  {teacher
                    ? "看看学生怎样理解两边的变化"
                    : "回看一次思考，再独立试一题"}
                </h3>
                <p>{teacher ? "原作答与帮助记录" : "等式性质 · 错题补救"}</p>
              </div>
              <Status>{teacher ? "待反馈" : "待复习"}</Status>
              <Button
                size="icon"
                variant="ghost"
                aria-label="打开复习与反馈"
                onClick={() => navigate(teacher ? "insights" : "repair")}
              >
                <ArrowUpRight />
              </Button>
            </div>
          </section>
          <section>
            <SectionHeading
              title={teacher ? "值得借鉴的教法" : "继续探索"}
              action={teacher ? "案例库" : "课程目录"}
              route={teacher ? "cases" : "courses"}
            />
            <div className="explore-grid">
              <button
                className="explore-card lilac"
                onClick={() => navigate(teacher ? "case-detail" : "courses")}
              >
                <div className="explore-art">
                  <Calculator size={48} strokeWidth={1.2} />
                  <span className="formula-detail">x + a = b</span>
                </div>
                <span className="explore-category">一元一次方程</span>
                <h3>
                  {teacher
                    ? "让学生说出“同时”的意义"
                    : "从相等关系，到方程求解"}
                </h3>
                <p>
                  {teacher
                    ? "教学案例 · 团队编写示例"
                    : "完整单元内容持续建设中"}
                </p>
                <ArrowUpRight className="explore-arrow" size={18} />
              </button>
              <button
                className="explore-card peach"
                onClick={() => navigate(teacher ? "cases" : "wrong")}
              >
                <div className="explore-art">
                  <BookOpen size={48} strokeWidth={1.2} />
                  <span className="formula-detail">理解 → 应用</span>
                </div>
                <span className="explore-category">
                  {teacher ? "教学经验" : "错题帮"}
                </span>
                <h3>
                  {teacher
                    ? "根据学生回应，调整讲法"
                    : "每一道错题，都有新的发现"}
                </h3>
                <p>
                  {teacher
                    ? "从一个问题，找到适合的引导"
                    : "保留原来的思考，找到下一步"}
                </p>
                <ArrowUpRight className="explore-arrow" size={18} />
              </button>
            </div>
          </section>
        </div>
        <aside className="home-aside">
          <Surface className="learning-rhythm">
            <div className="section-heading">
              <h2>{teacher ? "教学准备" : "本课进度"}</h2>
              <Target size={17} className="muted" />
            </div>
            <div className="rhythm-total">
              <strong>
                {completed ? "5" : "2"}
                <span>/ 5</span>
              </strong>
              <p>{teacher ? "已准备的教学环节" : "已完成的学习活动"}</p>
            </div>
            <div className="activity-dots">
              {["观察", "解释", "练习", "检查", "反馈"].map((label, index) => (
                <div key={label}>
                  <span className={index < (completed ? 5 : 2) ? "done" : ""}>
                    {index < (completed ? 5 : 2) ? (
                      <CircleCheck size={17} />
                    ) : (
                      <span className="dot-inner" />
                    )}
                  </span>
                  <small>{label}</small>
                </div>
              ))}
            </div>
            <div className="rhythm-note">
              <Sparkles size={15} />
              <span>
                {teacher
                  ? "内容可预览，也可随时调整"
                  : "每一步理解，都值得认真记录"}
              </span>
            </div>
          </Surface>
          <Surface className="next-step">
            <span className="tiny-label">下一步</span>
            <h2>{teacher ? "看看学生的真实思路" : "试试，你能独立完成吗？"}</h2>
            <p>
              {teacher
                ? "把原作答、获得的帮助和新题表现放在一起看。"
                : "用一道新题，看看刚才的理解是否真的属于自己。"}
            </p>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => navigate(teacher ? "insights" : "check")}
            >
              {teacher ? "查看学情反馈" : "开始独立检查"}
              <ArrowRight />
            </Button>
            <span className="time-note">
              <Clock3 size={13} />
              按自己的节奏完成
            </span>
          </Surface>
          <div className="small-learning-record">
            <div className="section-heading">
              <h3>学习留下的痕迹</h3>
              <HistoryIcon />
            </div>
            <div>
              <span>本地检查记录</span>
              <strong>{attempts.length} 次</strong>
            </div>
            <div>
              <span>独立答对的新题</span>
              <strong>
                {attempts.filter((item) => !item.helped && item.correct).length}{" "}
                次
              </strong>
            </div>
            <button onClick={() => navigate("records")}>
              查看学习记录
              <ChevronRight size={14} />
            </button>
          </div>
        </aside>
      </div>
    </>
  );
}
function HistoryIcon() {
  return <BookOpen size={15} className="muted" />;
}
export function Courses() {
  return (
    <>
      <PageHeading
        title="让知识，一课一课连接起来。"
        description="七年级数学 · 选择一个目标，按自己的节奏开始。"
      />
      <div className="course-collection">
        <div className="course-cover">
          <img src="/images/equation-balance.png" alt="一元一次方程课程封面" />
        </div>
        <div className="course-overview">
          <Status tone="blue">第一单元</Status>
          <h2>一元一次方程</h2>
          <p>从相等关系开始，用数学描述变化，理解每一步运算的意义。</p>
          <div className="course-facts">
            <span>
              <BookOpen size={15} />
              首课已开放
            </span>
            <span>
              <Target size={15} />
              观察、解释与应用
            </span>
          </div>
          <RouteButton route="learn">开始等式性质</RouteButton>
        </div>
      </div>
      <SectionHeading title="单元课时" />
      <Surface>
        <div className="lesson-row">
          <span className="lesson-number">1</span>
          <div>
            <h3>等式性质</h3>
            <p>理解两边共同变化的条件，尝试独立应用</p>
          </div>
          <Status tone="green">已开放</Status>
          <RouteButton route="learn" secondary>
            进入课时
          </RouteButton>
        </div>
        {["解简单的一元一次方程", "用方程解决生活问题"].map((name, index) => (
          <div className="lesson-row" key={name}>
            <span className="lesson-number">{index + 2}</span>
            <div>
              <h3>{name}</h3>
              <p>后续课时 · 内容正在建设</p>
            </div>
            <Status>待开放</Status>
          </div>
        ))}
      </Surface>
    </>
  );
}
export function Records() {
  const { attempts } = useLearning();
  return (
    <>
      <PageHeading
        title="每一次尝试，都有迹可循。"
        description="原作答、获得的帮助与后来的理解，都留在这里。"
      />
      <Surface>
        <SectionHeading title="等式性质 · 检查记录" />
        {attempts.length ? (
          attempts.map((attempt, index) => (
            <div className="record-row" key={index}>
              <span className="record-icon">
                <CircleCheck size={18} />
              </span>
              <div>
                <h3>
                  第 {index + 1} 次作答 · {attempt.answer}
                </h3>
                <p>{attempt.reason || "本次未填写解释"}</p>
              </div>
              <Status tone={attempt.correct ? "green" : "amber"}>
                {attempt.correct ? "数值正确" : "需要再练习"}
              </Status>
              <Status>{attempt.helped ? "获得帮助" : "独立作答"}</Status>
            </div>
          ))
        ) : (
          <EmptyState
            title="新的理解，将从这里开始"
            description="完成一道检查题后，可以回看自己的作答与思考。"
          >
            <RouteButton route="learn">开始学习</RouteButton>
          </EmptyState>
        )}
      </Surface>
    </>
  );
}
