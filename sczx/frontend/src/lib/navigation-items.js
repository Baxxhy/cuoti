import {LayoutDashboard,BookOpen,BookOpenText,NotebookPen,History,LibraryBig,Users,FileText,Layers,MessageSquareText} from '@/components/app/icons.js';
export const navigation={
 student:[['home','我的学习',LayoutDashboard],['courses','探索课程',BookOpen],['exams','我的考试',FileText],['live','我的课堂',Users],['wrong','我的错题',NotebookPen],['memory','复习',History],['records','学习记录',History],['class','我的班级',Users],['issues','问题与回复',MessageSquareText]],
 teacher:[['teacher','教学概览',LayoutDashboard],['cases','教学案例',LibraryBig],['courses','课程与课时',BookOpen],['prepare','我的教案',FileText],['exam-bank','题库',BookOpenText],['exam-papers','组卷与考试',FileText],['live','实时课堂',Users],['groups','分层教学',Users],['community','教研交流',LibraryBig],['class','班级教学',Users],['memory','学习记忆',History],['issues','问题与回复',MessageSquareText]],
 admin:[['manage','资料与案例',Layers],['content','课程内容',BookOpenText],['issues','管理与运行',MessageSquareText]],
};
