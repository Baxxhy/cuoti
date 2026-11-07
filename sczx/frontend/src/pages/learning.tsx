import type { PageProps } from "@/App";
import {
  ExperienceLink,
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
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Workspace } from "@/components/workspace";
import { navigate } from "@/lib/navigation";
import { questions, useLearning } from "@/store";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  ImagePlus,
  Lightbulb,
  Plus,
  RotateCcw,
  Send,
  Sparkles,
  Upload,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

export function Learning({ notify }: PageProps) {
  const { observation, update } = useLearning();
  const [weight, setWeight] = useState(0);
  const [draft, setDraft] = useState(observation);
  const [help, setHelp] = useState("");
  const [question, setQuestion] = useState("");
  const [activeTab, setActiveTab] = useState("observe");
  const [imageName, setImageName] = useState("");
  const primary = (
    <article className="lesson-paper">
      <div className="lesson-paper-heading">
        <span className="lesson-topic">观察与理解</span>
        <span className="reading-time">
          <Clock3 size={13} />
          按自己的节奏
        </span>
      </div>
      <h2>
        如果两边一起变化，
        <br />
        相等关系会改变吗？
      </h2>
      <p className="lesson-introduction">
        先观察这架平衡的天平。试着给两边增加相同数量，再解释你看到了什么。
      </p>
      <div className="interactive-balance">
        <div className="balance-math">
          <span>{5 + weight}</span>
          <span>=</span>
          <span>{5 + weight}</span>
        </div>
        <div className="balance-scene">
          <div className="balance-pillar" />
          <motion.div
            className="balance-arm"
            animate={{ rotate: weight % 2 ? [0, 3, -2, 0] : [0, -2, 2, 0] }}
            transition={{ duration: 0.6 }}
          >
            <div className="balance-dish left">
              <motion.div
                key={`l-${weight}`}
                initial={{ y: -8 }}
                animate={{ y: 0 }}
                className="balance-block"
              >
                5{weight > 0 && <span>+ {weight}</span>}
              </motion.div>
            </div>
            <div className="balance-dish right">
              <motion.div
                key={`r-${weight}`}
                initial={{ y: -8 }}
                animate={{ y: 0 }}
                className="balance-block"
              >
                5{weight > 0 && <span>+ {weight}</span>}
              </motion.div>
            </div>
          </motion.div>
        </div>
        <div className="balance-toolbar">
          <Status tone="green">
            <Check size={12} />
            两边仍然相等
          </Status>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setWeight((value) => value + 1)}
          >
            <Plus />
            两边同时加 1
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="重置天平"
            onClick={() => setWeight(0)}
          >
            <RotateCcw />
          </Button>
        </div>
      </div>
      <div className="lesson-explanation">
        <span className="explanation-icon">
          <Lightbulb size={19} />
        </span>
        <div>
          <h3>把观察写成数学</h3>
          <p>等式两边同时加上同一个数，结果仍然相等。</p>
          <div className="math-equation">
            a = b <span>⇒</span> a + c = b + c
          </div>
        </div>
      </div>
      <label className="field-label" htmlFor="observation">
        用自己的话解释一下
      </label>
      <Textarea
        id="observation"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="如果只改变左边，你认为会发生什么？"
      />
      <div className="paper-actions">
        <Button
          variant="outline"
          onClick={() => {
            update({ observation: draft });
            notify("你的解释已保存");
          }}
        >
          <Check size={15} />
          保存解释
        </Button>
        <RouteButton route="check">独立试一试</RouteButton>
      </div>
    </article>
  );
  const secondary = (
    <aside className="assistant-panel">
      <div className="assistant-title">
        <span className="assistant-symbol">
          <Sparkles size={19} />
        </span>
        <div>
          <h3>陪你多想一步</h3>
          <p>根据你的问题，换一种理解方式</p>
        </div>
      </div>
      <div className="assistant-message">
        <p>先想一想，天平平衡的时候，两边有什么共同的特点？</p>
        <p>你可以先预测，再点击操作验证自己的想法。</p>
      </div>
      <div className="help-options">
        <Button
          variant="outline"
          onClick={() =>
            setHelp(
              "例如 5 = 5，两边都加 2，得到 7 = 7。如果只给左边加 2，就变成 7 和 5。你能解释它们有什么不同吗？",
            )
          }
        >
          <Lightbulb />
          举个例子
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            setHelp(
              "把两边想成两组一样多的物品。两边增加同样多的物品，仍然一样多。只增加一边时，它们就不一样多了。",
            )
          }
        >
          <RotateCcw />
          换种讲法
        </Button>
      </div>
      <AnimatePresence>
        {help && (
          <motion.div
            className="assistant-answer"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <span>
              <Sparkles size={13} />
              演示指导
            </span>
            <p>{help}</p>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="assistant-compose">
        <Textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          aria-label="向学习助手提问"
          placeholder="写下你还没想明白的地方……"
        />
        <div>
          <label className="image-input" aria-label="选择题图">
            <ImagePlus size={18} />
            <input
              type="file"
              accept="image/*"
              onChange={(event) =>
                setImageName(event.target.files?.[0]?.name || "")
              }
            />
          </label>
          <span>{imageName || "支持上传题图"}</span>
          <Button
            size="icon"
            aria-label="发送问题"
            onClick={() => {
              if (!question.trim() && !imageName)
                return notify("先写下问题或选择题图");
              setHelp(
                `关于“${question || "你选择的题图"}”，我们可以先回到等式两边的变化。请比较两边进行的运算，再说说是否保持相等。此处为预设演示回应。`,
              );
              setQuestion("");
            }}
          >
            <Send />
          </Button>
        </div>
      </div>
      <ExperienceLink />
      <p className="assistant-disclaimer">
        原型指导为预设示例，后续接入教学案例与模型 API。
      </p>
    </aside>
  );
  return (
    <>
      <div className="back-line">
        <Button variant="ghost" size="sm" onClick={() => navigate("home")}>
          <ArrowLeft />
          返回我的学习
        </Button>
        <span>七年级数学 / 一元一次方程</span>
      </div>
      <PageHeading
        title="等式性质"
        description="从观察出发，解释等式两边共同变化的道理。"
      >
        <Status tone="blue">学习中</Status>
        <RouteButton route="result" secondary>
          学习结果
        </RouteButton>
      </PageHeading>
      <div className="learning-tabs">
        <Tabs
          value={activeTab}
          onValueChange={(value) => {
            setActiveTab(value);
            if (value === "check") navigate("check");
            if (value === "review") navigate("repair");
          }}
        >
          <TabsList>
            <TabsTrigger value="observe">观察与理解</TabsTrigger>
            <TabsTrigger value="check">独立检查</TabsTrigger>
            <TabsTrigger value="review">订正与补救</TabsTrigger>
          </TabsList>
        </Tabs>
        <span>
          本课活动 2 / 5<Progress value={40} aria-label="课时进度" />
        </span>
      </div>
      <Workspace primary={primary} secondary={secondary} />
    </>
  );
}
export function CheckLesson({ notify }: PageProps) {
  const { question, helped, update, addAttempt } = useLearning();
  const [answer, setAnswer] = useState("");
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const current = questions[question];
  function nextQuestion() {
    if (question + 1 >= questions.length)
      return notify("两道示例题已展示，可以保存结果，稍后继续");
    update({ question: question + 1, helped: false });
    setAnswer("");
    setReason("");
    setSubmitted(false);
  }
  return (
    <>
      <div className="back-line">
        <Button variant="ghost" onClick={() => navigate("learn")}>
          <ArrowLeft />
          返回本课
        </Button>
      </div>
      <PageHeading
        title="把理解，交给一道新题。"
        description="先试着独立完成，需要时也可以获得帮助。"
      />
      <div className="check-grid">
        <Surface className="question-card">
          <div className="question-meta">
            <span>等式性质 · 检查题 {question + 1}</span>
            <Status tone={helped ? "amber" : "green"}>
              {helped ? "本题获得过帮助" : "独立尝试"}
            </Status>
          </div>
          <h2>{current.prompt}</h2>
          <div className="question-equation">{current.equation}</div>
          <label className="field-label" htmlFor="answer">
            你的答案
          </label>
          <Input
            id="answer"
            value={answer}
            onChange={(event) => {
              setAnswer(event.target.value);
              setSubmitted(false);
            }}
            inputMode="decimal"
            placeholder="填写数值"
          />
          <label className="field-label" htmlFor="reason">
            你是怎样保持等式成立的？
          </label>
          <Textarea
            id="reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="说明两边进行了什么运算……"
          />
          <AnimatePresence>
            {helped && (
              <motion.div
                className="inline-notice"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
              >
                <Lightbulb size={17} />
                <div>
                  <strong>一点提示</strong>
                  <p>{current.hint}</p>
                  <small>本题会记录帮助情况，理解后可以换新题。</small>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          {submitted && (
            <div className="inline-notice">
              <CheckCircle2 size={18} />
              <div>
                <strong>
                  {answer.trim() === current.answer
                    ? "数值正确，看看你的解释是否完整。"
                    : "再想一想，两边进行了相同的运算吗？"}
                </strong>
                <p>
                  {helped
                    ? "本次获得过帮助，下一题再试试独立完成。"
                    : "已保存本次独立作答，解释内容可由教师查看。"}
                </p>
              </div>
            </div>
          )}
          <div className="paper-actions">
            <Button
              disabled={submitted}
              onClick={() => {
                if (!answer.trim()) return notify("请先填写答案");
                addAttempt({
                  question,
                  answer,
                  reason,
                  helped,
                  correct: answer.trim() === current.answer,
                });
                setSubmitted(true);
                notify("本次作答已保存");
              }}
            >
              {submitted ? "作答已保存" : "提交作答"}
              <ArrowRight />
            </Button>
            <Button variant="ghost" onClick={() => update({ helped: true })}>
              <CircleHelp />
              我需要提示
            </Button>
          </div>
        </Surface>
        <aside className="check-aside">
          <span className="check-aside-icon">
            <TargetIcon />
          </span>
          <h2>理解，可以多试一次。</h2>
          <p>
            使用帮助后，当前题会作为指导练习保留。下一道新题，将重新记录你的独立表现。
          </p>
          <Button variant="outline" onClick={nextQuestion}>
            换一道新题
            <ArrowRight />
          </Button>
          <Button variant="ghost" onClick={() => navigate("result")}>
            保存并稍后继续
            <ChevronRight />
          </Button>
          <p className="small-caption">
            演示包含两道检查题，所有尝试都可回看。
          </p>
        </aside>
      </div>
    </>
  );
}
function TargetIcon() {
  return <CheckCircle2 size={28} strokeWidth={1.3} />;
}
export function Result({ notify }: PageProps) {
  const { attempts, completed, feedback, update, repaired } = useLearning();
  const independent = attempts.filter((item) => item.correct && !item.helped);
  return (
    <>
      <PageHeading
        title="看见自己，正在理解。"
        description="等式性质 · 本课的每一步都有记录。"
      >
        <RouteButton route="learn" secondary>
          返回本课
        </RouteButton>
      </PageHeading>
      <div className="result-banner">
        <span>
          <CheckCircle2 size={32} strokeWidth={1.4} />
        </span>
        <div>
          <h2>{completed ? "本课学习结果已提交" : "把这次学习，整理一下"}</h2>
          <p>你可以回看作答、继续补救，或把当前结果提交给教师。</p>
        </div>
        <Button
          onClick={() => {
            update({ completed: true });
            notify("本课结果已模拟提交给教师");
          }}
        >
          {completed ? "再次提交结果" : "提交本课结果"}
          <ArrowRight />
        </Button>
      </div>
      <div className="two-column">
        <Surface>
          <SectionHeading title="本次学习记录" />
          {[
            {
              title: "检查题尝试",
              text: `${attempts.length} 次作答，原答案和解释均已记录`,
              route: "records",
            },
            {
              title: "独立应用",
              text: `${independent.length} 次未使用帮助且数值正确`,
              route: "check",
            },
            {
              title: "错题补救",
              text: repaired
                ? "已完成一次变式尝试"
                : "还可以回看等式两边的共同变化",
              route: "repair",
            },
          ].map((item) => (
            <button
              className="result-row"
              key={item.title}
              onClick={() => navigate(item.route)}
            >
              <CheckCircle2 size={18} />
              <span>
                <strong>{item.title}</strong>
                <small>{item.text}</small>
              </span>
              <ChevronRight size={17} />
            </button>
          ))}
        </Surface>
        <Surface className="teacher-feedback">
          <div className="feedback-avatar">
            <span>师</span>
            <div>
              <h3>教师的反馈</h3>
              <p>演示反馈 · 可在教师端修改</p>
            </div>
          </div>
          <blockquote>{feedback}</blockquote>
          <RouteButton route="check" secondary>
            继续检查新题
          </RouteButton>
        </Surface>
      </div>
    </>
  );
}
export function WrongQuestions({ notify }: PageProps) {
  const { wrongQuestion, originalImage, update, repaired } = useLearning();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(wrongQuestion);
  const [image, setImage] = useState(originalImage);
  const [filter, setFilter] = useState("all");
  const showQuestion =
    filter === "all" ||
    (filter === "pending" && !repaired) ||
    (filter === "done" && repaired);
  return (
    <>
      <PageHeading
        title="把没想明白的，再想明白。"
        description="保留原题和当时的思考，让每一道错题成为下一步。"
      >
        <Button onClick={() => setOpen(true)}>
          <Plus />
          录入一道题
        </Button>
      </PageHeading>
      <div className="wrong-summary">
        <NotebookSymbol />
        <div>
          <h2>我的错题本</h2>
          <p>一元一次方程 · 1 道演示题</p>
        </div>
        <Status tone={repaired ? "green" : "amber"}>
          {repaired ? "已订正，待复习" : "待补救 1 道"}
        </Status>
      </div>
      <Tabs value={filter} onValueChange={setFilter}>
        <TabsList>
          <TabsTrigger value="all">全部错题</TabsTrigger>
          <TabsTrigger value="pending">待补救</TabsTrigger>
          <TabsTrigger value="done">已订正</TabsTrigger>
        </TabsList>
      </Tabs>
      {showQuestion ? (
        <div className="wrong-layout">
          <Surface className="wrong-question">
            <div className="question-meta">
              <Status>等式性质</Status>
              <span>来自课程随堂练习 · 演示</span>
            </div>
            <h2>{wrongQuestion}</h2>
            {originalImage && (
              <img
                className="uploaded-image"
                src={originalImage}
                alt="本地选择的原始题图"
              />
            )}
            <div className="original-attempt">
              <span>原来的作答</span>
              <div className="math-equation">x = 8 + 3</div>
              <span className="mistake-note">
                左边去掉了 3，右边应该怎样变化？
              </span>
            </div>
            <div className="paper-actions">
              <RouteButton route="repair">开始补救</RouteButton>
              <Button variant="ghost" onClick={() => navigate("result")}>
                查看来源任务
                <ArrowUpRightIcon />
              </Button>
            </div>
          </Surface>
          <div className="wrong-guidance">
            <Lightbulb size={27} strokeWidth={1.3} />
            <h3>答案背后，还有思路。</h3>
            <p>
              先看看当时为什么这样做，再通过提示、讲解和新题，建立自己的理解。
            </p>
            <ExperienceLink />
          </div>
        </div>
      ) : (
        <Surface>
          <div className="empty-state">
            <h3>这个分类还没有题目</h3>
            <p>完成补救后，可以在“已订正”中回看。</p>
          </div>
        </Surface>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="upload-dialog">
          <DialogHeader>
            <DialogTitle>把题目放进错题本</DialogTitle>
            <DialogDescription>
              选择原图或填写题目，确认后开始补救。
            </DialogDescription>
          </DialogHeader>
          <label className="upload-dropzone">
            <Upload size={26} />
            <strong>点击选择题图</strong>
            <span>图片仅用于当前浏览器内的原型预览</span>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = () => setImage(String(reader.result));
                reader.readAsDataURL(file);
              }}
            />
          </label>
          {image && (
            <img
              className="upload-thumbnail"
              src={image}
              alt="已选择的原始题图"
            />
          )}
          <label className="field-label" htmlFor="question-text">
            确认题目文字
          </label>
          <Textarea
            id="question-text"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <p className="small-caption">
            当前补救演示针对 x + 3 = 8。自定义题目的智能识别与生成在后续接入。
          </p>
          <Button
            onClick={() => {
              if (!text.trim()) return notify("请先填写题目");
              update({ wrongQuestion: text, originalImage: image });
              setOpen(false);
              notify("题目已保存在当前演示错题本");
            }}
          >
            确认保存
            <ArrowRight />
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
function NotebookSymbol() {
  return (
    <span className="notebook-symbol">
      <BookOpen size={25} strokeWidth={1.5} />
    </span>
  );
}
function ArrowUpRightIcon() {
  return <ChevronRight size={15} />;
}
export function Repair({ notify }: PageProps) {
  const { update } = useLearning();
  const [answer, setAnswer] = useState("");
  const [reason, setReason] = useState("");
  const [checked, setChecked] = useState(false);
  return (
    <>
      <div className="back-line">
        <Button variant="ghost" onClick={() => navigate("wrong")}>
          <ArrowLeft />
          返回错题帮
        </Button>
      </div>
      <PageHeading
        title="两边的变化，要保持一致。"
        description="回看最初的想法，再给自己一次独立完成的机会。"
      >
        <RouteButton route="result" secondary>
          返回原任务
        </RouteButton>
      </PageHeading>
      <div className="two-column">
        <Surface className="repair-paper">
          <Status tone="amber">原作答回看</Status>
          <h2>为什么这里需要减去 3？</h2>
          <div className="original-attempt">
            <div className="math-equation">
              x + 3 = 8<br />
              <span className="incorrect-step">x = 8 + 3</span>
            </div>
          </div>
          <p>左边去掉了 3，右边却增加了 3。我们对两边做的是同一件事吗？</p>
          <div className="correct-method">
            <Lightbulb size={18} />
            <div>
              <h3>先把完整过程写下来</h3>
              <div className="math-equation">
                x + 3 − 3 = 8 − 3<br />x = 5
              </div>
            </div>
          </div>
          <ExperienceLink />
        </Surface>
        <Surface className="repair-practice">
          <span className="tiny-label">再试一次</span>
          <h2>换个数字，解释你的方法。</h2>
          <div className="question-equation">z + 2 = 9</div>
          <label className="field-label" htmlFor="repair-answer">
            z 的值是多少？
          </label>
          <Input
            id="repair-answer"
            value={answer}
            onChange={(event) => {
              setAnswer(event.target.value);
              setChecked(false);
            }}
            inputMode="decimal"
            placeholder="填写数值"
          />
          <label className="field-label" htmlFor="repair-reason">
            你对两边进行了什么运算？
          </label>
          <Textarea
            id="repair-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="两边同时……"
          />
          {checked && (
            <div className="inline-notice">
              <CheckCircle2 size={18} />
              <p>
                {answer.trim() === "7"
                  ? "正确。两边同时减去 2，得到 z = 7。"
                  : "试着在两边同时减去 2，再计算右边。"}
              </p>
            </div>
          )}
          <div className="paper-actions">
            <Button
              onClick={() => {
                if (!answer.trim()) return notify("请先填写答案");
                update({ repaired: answer.trim() === "7" });
                setChecked(true);
                notify("这次补救尝试已记录");
              }}
            >
              提交尝试
              <ArrowRight />
            </Button>
            <Button variant="ghost" onClick={() => navigate("result")}>
              返回任务
            </Button>
          </div>
        </Surface>
      </div>
    </>
  );
}
