"""Student projection must never rewrite immutable teacher/task records."""
import copy
import unittest
from sczx_business.curriculum import student_content


class StudentReadingTests(unittest.TestCase):
    def test_explicit_student_reading_keeps_teacher_original(self):
        snapshot = {'blocks': [{'id': 'b', 'title': '教师标题', 'content': '出示例题。',
                               'studentTitle': '共同运算', 'studentContent': '等式两边同时加3。',
                               'teacherQuestion': '为什么两边相等？'}],
                    'questions': [{'id': 'q', 'answer': '8', 'explanation': '两边加3'}]}
        before = copy.deepcopy(snapshot)
        result = student_content(snapshot)
        self.assertEqual(snapshot, before)
        self.assertEqual(result['blocks'][0]['content'], '等式两边同时加3。')
        self.assertEqual(result['blocks'][0]['title'], '共同运算')
        self.assertNotIn('teacherQuestion', result['blocks'][0])
        self.assertNotIn('studentContent', result['blocks'][0])
        self.assertNotIn('answer', result['questions'][0])

    def test_legacy_agent_task_uses_its_frozen_lesson(self):
        snapshot = {'blocks': [{'id': 'b', 'title': '引导学生', 'content': '出示等式。',
                                'agentJobId': 'old-job'}],
                    'lessonSnapshot': {'versionId': 'old-version', 'blocks': [
                        {'id': 'b', 'title': '等式性质', 'content': '等式两边同加3仍相等。'}]}}
        before = copy.deepcopy(snapshot)
        self.assertEqual(student_content(snapshot)['blocks'][0]['content'], '等式两边同加3仍相等。')
        self.assertEqual(snapshot, before)

    def test_manual_student_language_is_not_keyword_filtered(self):
        snapshot = {'blocks': [{'id': 'b', 'title': '独立检查',
                                'content': '学生独立检查：除数是否非零？'}]}
        self.assertEqual(student_content(snapshot), snapshot)
