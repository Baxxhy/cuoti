import { InfoTip } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
Dialog,
DialogContent,
DialogDescription,
DialogHeader,
DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
Select,
SelectContent,
SelectItem,
SelectTrigger,
SelectValue,
} from "@/components/ui/select";
import {
Sheet,
SheetContent,
SheetDescription,
SheetTitle,
} from "@/components/ui/sheet";
import {
Tooltip,
TooltipContent,
TooltipProvider,
TooltipTrigger,
} from "@/components/ui/tooltip";
import { navigate } from "@/lib/navigation";
import { Courses,Home,Records } from "@/pages/home";
import {
CheckLesson,
Learning,
Repair,
Result,
WrongQuestions,
} from "@/pages/learning";
import { Issues,Manage } from "@/pages/manage";
import {
CaseDetail,
Cases,
Classroom,
Insights,
Prepare,
} from "@/pages/teacher";
import type { LucideIcon } from "lucide-react";
import {
ArrowUpRight,
Bell,
BookOpen,
BookOpenText,
Check,
ChevronDown,
ChevronRight,
CircleHelp,
FileText,
GraduationCap,
History,
Layers,
LayoutDashboard,
LibraryBig,
Menu,
MessageSquareText,
NotebookPen,
Search,
Settings2,
Users,
} from "lucide-react";
import {
AnimatePresence,
motion,
MotionConfig,
useReducedMotion,
} from "motion/react";
import { useEffect,useState } from "react";

type NavItem = { route: string; label: string; icon: LucideIcon };
const navigation: Record<string, NavItem[]> = {
  student: [
    { route: "home", label: "我的学习", icon: LayoutDashboard },
    { route: "courses", label: "探索课程", icon: BookOpen },
    { route: "wrong", label: "错题帮", icon: NotebookPen },
    { route: "records", label: "学习记录", icon: History },
  ],
  teacher: [
    { route: "teacher", label: "教学概览", icon: LayoutDashboard },
    { route: "cases", label: "教学案例", icon: LibraryBig },
    { route: "prepare", label: "我的教案", icon: FileText },
    { route: "class", label: "班级教学", icon: Users },
  ],
  admin: [
    { route: "manage", label: "内容工作台", icon: Layers },
    { route: "content", label: "课程内容", icon: BookOpenText },
    { route: "issues", label: "反馈与运行", icon: MessageSquareText },
  ],
};
const roleLabels: Record<string, string> = {
  student: "学生空间",
  teacher: "教师空间",
  admin: "内容管理",
};
const teacherRoutes = [
  "teacher",
  "cases",
  "case-detail",
  "prepare",
  "class",
  "insights",
];
const adminRoutes = ["manage", "content", "issues"];
export type PageProps = { notify: (message: string) => void };

function App() {
  const [route, setRoute] = useState(window.location.hash.slice(1) || "home");
  const [notice, setNotice] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [notifications, setNotifications] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const reducedMotion = useReducedMotion();
  const role = teacherRoutes.includes(route)
    ? "teacher"
    : adminRoutes.includes(route)
      ? "admin"
      : "student";
  const active =
    route === "learn" || route === "check" || route === "result"
      ? "home"
      : route === "repair"
        ? "wrong"
        : route === "case-detail"
          ? "cases"
          : route === "insights"
            ? "class"
            : route;

  useEffect(() => {
    const onRoute = () => {
      setRoute(window.location.hash.slice(1) || "home");
      setMobileOpen(false);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onRoute);
    return () => window.removeEventListener("hashchange", onRoute);
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, []);
  const props = { notify: setNotice };
  const pages: Record<string, React.ReactNode> = {
    home: <Home />,
    courses: <Courses />,
    records: <Records />,
    learn: <Learning {...props} />,
    check: <CheckLesson {...props} />,
    result: <Result {...props} />,
    wrong: <WrongQuestions {...props} />,
    repair: <Repair {...props} />,
    teacher: <Home teacher />,
    cases: <Cases />,
    "case-detail": <CaseDetail {...props} />,
    prepare: <Prepare {...props} />,
    class: <Classroom {...props} />,
    insights: <Insights {...props} />,
    manage: <Manage {...props} />,
    content: <Manage {...props} course />,
    issues: <Issues {...props} />,
  };
  const sidebar = (
    <>
      <a href="#home" className="wordmark" aria-label="师承智学首页">
        <span className="brand-symbol">
          <BookOpenText size={23} strokeWidth={1.8} />
        </span>
        <span>师承智学</span>
      </a>
      <div className="workspace-switch">
        <Select
          value={role}
          onValueChange={(value) =>
            navigate(
              value === "teacher"
                ? "teacher"
                : value === "admin"
                  ? "manage"
                  : "home",
            )
          }
          items={roleLabels}
        >
          <SelectTrigger aria-label="切换演示身份">
            <span className="workspace-icon">
              <GraduationCap size={17} />
            </span>
            <SelectValue />
            <ChevronDown className="role-chevron" />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(roleLabels).map(([value, label]) => (
              <SelectItem value={value} key={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="nav-label">
        {role === "student"
          ? "学习空间"
          : role === "teacher"
            ? "教学空间"
            : "工作空间"}
      </div>
      <nav aria-label="主要导航">
        {navigation[role].map((item) => (
          <motion.a
            key={item.route}
            href={`#${item.route}`}
            whileHover={reducedMotion ? {} : { x: 2 }}
            className={active === item.route ? "nav-item active" : "nav-item"}
            aria-current={active === item.route ? "page" : undefined}
          >
            <item.icon size={18} strokeWidth={1.7} />
            <span>{item.label}</span>
            {active === item.route && (
              <motion.span layoutId="nav-dot" className="nav-dot" />
            )}
          </motion.a>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <Button
          variant="ghost"
          className="utility-button"
          onClick={() => setHelpOpen(true)}
        >
          <CircleHelp />
          帮助与反馈
        </Button>
        <div className="profile">
          <span className="avatar">
            {role === "student" ? "林" : role === "teacher" ? "师" : "管"}
          </span>
          <span>
            <strong>
              {role === "student"
                ? "小林同学"
                : role === "teacher"
                  ? "教师演示账号"
                  : "内容管理账号"}
            </strong>
          </span>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="账号说明"
            onClick={() => setHelpOpen(true)}
          >
            <Settings2 />
          </Button>
        </div>
      </div>
    </>
  );
  const searchResults = [
    { route: "learn", title: "等式性质", subtitle: "七年级数学 · 第 1 课" },
    { route: "wrong", title: "错题帮", subtitle: "错题记录" },
    {
      route: "cases",
      title: "天平与等式 · 教学案例",
      subtitle: "教学案例",
    },
  ].filter((item) => (item.title + item.subtitle).includes(search));
  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider>
        <div className="app-shell">
          <aside className="desktop-sidebar">{sidebar}</aside>
          <div className="app-body">
            <header className="topbar">
              <div className="topbar-start">
                <Button
                  variant="ghost"
                  size="icon"
                  className="mobile-menu"
                  aria-label="打开导航菜单"
                  onClick={() => setMobileOpen(true)}
                >
                  <Menu />
                </Button>
                <span className="topbar-breadcrumb">
                  {roleLabels[role]}
                  <ChevronRight size={13} />
                  <strong>
                    {navigation[role].find((item) => item.route === active)
                      ?.label || "学习工作区"}
                  </strong>
                </span>
              </div>
              <div className="topbar-actions">
                <Button
                  variant="ghost"
                  className="search-trigger"
                  onClick={() => setSearchOpen(true)}
                >
                  <Search size={16} />
                  <span>搜索课程、案例</span>
                  <kbd>⌘ K</kbd>
                </Button>
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="查看消息"
                        onClick={() => setNotifications(true)}
                      />
                    }
                  >
                    <Bell size={18} />
                  </TooltipTrigger>
                  <TooltipContent>消息与提醒</TooltipContent>
                </Tooltip>
                <span className="topbar-demo">
                  演示
                  <InfoTip label="演示范围">
                    数据为演示；模型生成和发布采用本地模拟，学习记录保存在当前浏览器。
                  </InfoTip>
                </span>
              </div>
            </header>
            <main>
              <AnimatePresence mode="wait">
                <motion.div
                  key={route}
                  className="page-content"
                  initial={reducedMotion ? false : { opacity: 0, y: 9 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.2 }}
                >
                  {pages[route] || <Home />}
                </motion.div>
              </AnimatePresence>
            </main>
          </div>
        </div>
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="mobile-sidebar">
            <SheetTitle className="sr-only">主要导航</SheetTitle>
            <SheetDescription className="sr-only">
              切换身份或进入学习页面
            </SheetDescription>
            {sidebar}
          </SheetContent>
        </Sheet>
        <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
          <DialogContent className="search-dialog">
            <DialogHeader>
              <DialogTitle>搜索学习内容</DialogTitle>
              <DialogDescription className="sr-only">
                查找课程、错题与教学案例
              </DialogDescription>
            </DialogHeader>
            <Input
              autoFocus
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="试试“等式”或“天平”"
              aria-label="搜索内容"
            />
            <div className="search-results">
              {searchResults.map((item) => (
                <button
                  key={item.route}
                  onClick={() => {
                    navigate(item.route);
                    setSearchOpen(false);
                  }}
                >
                  <BookOpen size={20} />
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.subtitle}</small>
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              ))}
              {!searchResults.length && (
                <p className="muted">没有匹配结果，请尝试其他关键词。</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
        <Dialog open={notifications} onOpenChange={setNotifications}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>消息与提醒</DialogTitle>
              <DialogDescription className="sr-only">
                演示任务的最新动态
              </DialogDescription>
            </DialogHeader>
            <button
              className="notification-row"
              onClick={() => {
                navigate("result");
                setNotifications(false);
              }}
            >
              <span className="notification-dot" />
              <span>
                <strong>等式性质 · 查看学习反馈</strong>
              </span>
              <ChevronRight size={16} />
            </button>
          </DialogContent>
        </Dialog>
        <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>体验师承智学</DialogTitle>
              <DialogDescription className="sr-only">
                通过空间切换体验学生、教师与内容管理流程。
              </DialogDescription>
            </DialogHeader>
            <p className="dialog-copy">
              当前为本地交互原型。学习记录、教案和反馈保存在当前浏览器，模型生成及任务发布采用演示操作。
            </p>
            <label className="field-label" htmlFor="issue-note">
              留下体验反馈
            </label>
            <textarea
              id="issue-note"
              className="feedback-input"
              placeholder="告诉我们哪里需要改进"
            />
            <Button
              onClick={() => {
                sessionStorage.setItem(
                  "shicheng-experience-feedback",
                  (document.querySelector("#issue-note") as HTMLTextAreaElement)
                    ?.value || "",
                );
                setHelpOpen(false);
                setNotice("体验反馈已保存到本次浏览会话");
              }}
            >
              记录反馈
            </Button>
          </DialogContent>
        </Dialog>
        <AnimatePresence>
          {notice && (
            <motion.div
              className="toast-message"
              role="status"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
            >
              <Check size={16} />
              {notice}
            </motion.div>
          )}
        </AnimatePresence>
      </TooltipProvider>
    </MotionConfig>
  );
}
export default App;
