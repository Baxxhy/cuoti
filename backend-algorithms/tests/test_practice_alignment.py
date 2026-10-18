import asyncio

from practice_alignment import TopicDecisions, align_practice, linear_task
from retrieval_compute import prepare_query


def check(text, provider=None, name="一元一次方程"):
    return asyncio.run(
        align_practice(
            provider,
            {"question_text": "解方程2x+3=11"},
            {"name": name},
            [{"question": {"id": "candidate", "question_text": text}}],
        )
    )["checks"][0]


def test_linear_scope_and_real_route_counterexample():
    assert linear_task("解方程：3*x+4=19")
    assert linear_task("求解方程：1.5*x+3=9")
    assert not linear_task("已知2x+3=11，求x的平方")
    assert not linear_task("x**2=4")
    assert not linear_task("1/x=3")
    assert check("求解方程：4*x-7=9")["aligned"]
    assert not check("如图，比较甲乙丙三人行进路线长度的大小关系")["aligned"]


def test_model_must_ground_decision_and_linear_witness():
    class Provider:
        def __init__(self, decision):
            self.decision = decision

        async def generate_structured(self, prompt, schema):
            assert schema is TopicDecisions
            return {"decisions": [self.decision]}

    route = "比较甲乙丙行进路线的长度大小关系"
    decision = {
        "id": "candidate",
        "objective": "solve_linear",
        "source_quote": "2x+3=11",
        "candidate_quote": "长度大小关系",
        "linear_equation": "2x+3=11",
    }
    assert not check(route, Provider(decision))["aligned"]
    text = "一元一次方程3x+4=19，求x的值"
    decision.update(candidate_quote="求x的值", linear_equation="3x+4=19")
    assert check(text, Provider(decision))["aligned"]
    decision["candidate_quote"] = "题干里没有这段话"
    assert not check(text, Provider(decision))["aligned"]
    decision.update(candidate_quote="求x的值", id="invented-id")
    assert not check(text, Provider(decision))["aligned"]


def test_other_subjects_keep_structured_semantic_admission():
    class Provider:
        async def generate_structured(self, prompt, schema):
            return schema(
                decisions=[
                    {
                        "id": "candidate",
                        "objective": "same_skill",
                        "source_quote": "平衡原子个数",
                        "candidate_quote": "配平",
                    }
                ]
            )

    result = asyncio.run(
        align_practice(
            Provider(),
            {"question_text": "这条反应式需要平衡原子个数"},
            {"name": "化学方程式"},
            [{"question": {"id": "candidate", "question_text": "请配平下列化学反应"}}],
        )
    )
    assert result["checks"][0]["aligned"]


def test_prepare_does_not_guess_the_first_card_when_no_topic_evidence():
    card = {"id": "id", "name": "化学方程式", "code": "001", "content": {}}
    source = {
        "subject": "化学",
        "grade": "初三",
        "title": "一道题",
        "question_text": "尚未核对的内容",
        "knowledge_points": [],
    }
    assert (
        prepare_query(source, None, {}, [card], "practice", "reinforce")[
            "target_knowledge_id"
        ]
        is None
    )
    source.update(subject="数学", question_text="解方程2x+3=11")
    card.update(name="一元一次方程")
    assert (
        prepare_query(source, None, {}, [card], "practice", "reinforce")[
            "target_knowledge_id"
        ]
        == "id"
    )
