import {
EmptyState,
PageHeading,
RouteButton,
SectionHeading,
Status,
Surface,
} from "@/components/common";
import { Button } from "@/components/ui/button";
import { navigate } from "@/lib/navigation";
import { useLearning } from "@/store";
import {
ArrowRight,
ArrowUpRight,
BookOpen,
Calculator,
ChevronRight,
CircleCheck,
FileText,
Lightbulb,
Target,
} from "lucide-react";
import { motion } from "motion/react";

export function Home({ teacher = false }: { teacher?: boolean }) {
  const { published, completed, attempts } = useLearning();
  return (
    <>
      <PageHeading title={teacher ? "教学概览" : "我的学习"} />
      <div className="home-grid">
        <div className="home-main">
          <motion.section className="lesson-hero" whileHover={{ y: -2 }}>
            <img
              src="/images/equation-balance.png"
              alt="等式性质课程的天平封面"
              fetchPriority="high"
            />
            <div className="hero-copy">
              <span className="hero-category">七年级数学 · 一元一次方程</span>
              <h2>等式性质</h2>
              <Button
                onClick={() => navigate(teacher ? "prepare" : "learn")}
                size="lg"
              >
                {teacher ? "继续备课" : completed ? "回看本课" : "继续学习"}
                <ArrowRight size={16} />
              </Button>
            </div>
          </motion.section>
          <section className="task-section">
            <SectionHeading
              title={teacher ? "班级任务" : "学习任务"}
              action="全部任务"
              route={teacher ? "class" : "courses"}
            />
            <div className="task-row">
              <span className="task-icon blue">
                <FileText size={20} />
              </span>
              <div className="task-description">
                <h3>等式性质</h3>
                <p>七年级一班</p>
              </div>
              <Status tone={completed ? "green" : "blue"}>
                {completed ? "已提交" : published ? "已发布" : "学习中"}
              </Status>
              <Button
                variant="ghost"
                onClick={() => navigate(teacher ? "insights" : "learn")}
              >
                {teacher ? "查看作答" : "继续"}
                <ChevronRight />
              </Button>
            </div>
            <div className="task-row">
              <span className="task-icon amber">
                <Lightbulb size={20} />
              </span>
              <div className="task-description">
                <h3>{teacher ? "等式性质 · 待反馈" : "等式性质 · 错题订正"}</h3>
              </div>
              <Status>{teacher ? "待反馈" : "待复习"}</Status>
              <Button
                variant="ghost"
                onClick={() => navigate(teacher ? "insights" : "repair")}
              >
                {teacher ? "查看" : "订正"}
                <ChevronRight />
              </Button>
            </div>
          </section>
          <section>
            <SectionHeading title={teacher ? "教学资源" : "学习入口"} />
            <div className="explore-grid">
              <button
                className="explore-card lilac"
                onClick={() => navigate(teacher ? "case-detail" : "courses")}
              >
                <div className="explore-art">
                  <Calculator size={48} strokeWidth={1.2} />
                  <span className="formula-detail">x + a = b</span>
                </div>
                <h3>{teacher ? "天平与等式性质" : "一元一次方程"}</h3>
                <ArrowUpRight className="explore-arrow" size={18} />
              </button>
              <button
                className="explore-card peach"
                onClick={() => navigate(teacher ? "cases" : "wrong")}
              >
                <div className="explore-art">
                  <BookOpen size={48} strokeWidth={1.2} />
                </div>
                <h3>{teacher ? "教学案例" : "错题帮"}</h3>
                <ArrowUpRight className="explore-arrow" size={18} />
              </button>
            </div>
          </section>
        </div>
        <aside className="home-aside">
          <Surface className="learning-rhythm">
            <div className="section-heading">
              <h2>本课进度</h2>
              <Target size={17} className="muted" />
            </div>
            <div className="rhythm-total">
              <strong>
                {completed ? "5" : "2"}
                <span>/ 5</span>
              </strong>
              <p>已完成活动</p>
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
          </Surface>
          <Surface className="next-step">
            <h2>{teacher ? "学情反馈" : "独立检查"}</h2>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => navigate(teacher ? "insights" : "check")}
            >
              {teacher ? "查看学生作答" : "开始检查"}
              <ArrowRight />
            </Button>
          </Surface>
          <div className="small-learning-record">
            <div className="section-heading">
              <h3>检查记录</h3>
            </div>
            <div>
              <span>尝试次数</span>
              <strong>{attempts.length} 次</strong>
            </div>
            <div>
              <span>独立答对</span>
              <strong>
                {attempts.filter((item) => !item.helped && item.correct).length}{" "}
                次
              </strong>
            </div>
            <button onClick={() => navigate("records")}>
              全部记录
              <ChevronRight size={14} />
            </button>
          </div>
        </aside>
      </div>
    </>
  );
}
export function Courses() {
  return (
    <>
      <PageHeading title="课程" />
      <div className="course-collection">
        <div className="course-cover">
          <img src="/images/equation-balance.png" alt="一元一次方程课程封面" />
        </div>
        <div className="course-overview">
          <Status tone="blue">七年级数学</Status>
          <h2>一元一次方程</h2>
          <RouteButton route="learn">开始等式性质</RouteButton>
        </div>
      </div>
      <SectionHeading title="单元课时" />
      <Surface>
        <div className="lesson-row">
          <span className="lesson-number">1</span>
          <div>
            <h3>等式性质</h3>
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
      <PageHeading title="学习记录" />
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
                {attempt.reason && <p>{attempt.reason}</p>}
              </div>
              <Status tone={attempt.correct ? "green" : "amber"}>
                {attempt.correct ? "数值正确" : "需订正"}
              </Status>
              <Status>{attempt.helped ? "获得帮助" : "独立作答"}</Status>
            </div>
          ))
        ) : (
          <EmptyState title="暂无检查记录">
            <RouteButton route="check">开始检查</RouteButton>
          </EmptyState>
        )}
      </Surface>
    </>
  );
}
