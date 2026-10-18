import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from service import create_app

REFERENCE = r"""
import asyncio,json,sys
from types import SimpleNamespace
import app.services.agent_runtime as original
import agent_compute as migrated
from app.services.tutor_graph import run_tutor_step
rows=json.load(sys.stdin)
a=original.build_memory_snapshot(*[[SimpleNamespace(**r) for r in items] for items in rows])
b=migrated.build_memory_snapshot(*[[SimpleNamespace(**r) for r in items] for items in rows])
assert a.model_dump()==b.model_dump()
async def compare():
    for message in ['不会','提示一下','我觉得但不知道下一步','新错误单位','只要答案','x=4','根据条件求解']:
        graph=dict(run_tutor_step(3,message,1,0,{'subject':'数学','question_type':'综合题','final_answer':'x=4','reference_steps':['2x=8','x=4']}))
        for tool in original.TOOL_DESCRIPTIONS:
            graph['tool_name']=tool
            p=original.fallback_plan(graph,a);q=migrated.fallback_plan(graph,b)
            assert p.model_dump()==q.model_dump()
            c=original.AgentToolContext('数学','综合题','求解','x=4',['2x=8','x=4'],message,3,['一次方程'],a)
            d=migrated.AgentToolContext('数学','综合题','求解','x=4',['2x=8','x=4'],message,3,['一次方程'],b)
            x=await original.execute_agent_tool(None,p,c);y=await migrated.execute_agent_tool(None,q,d)
            assert x.model_dump()==y.model_dump(),(tool,x,y)
            assert original.verify_decision(p,x,a).model_dump()==migrated.verify_decision(q,y,b).model_dump()
            assert original.ground_reply_with_tool(graph['reply'],x)==migrated.ground_reply_with_tool(graph['reply'],y)
    cards=[SimpleNamespace(code='EQ',name='一次方程',content={'definition':'等式两边作相同运算'})]
    async def lookup(*args,**kwargs): return cards
    original.search_knowledge_cards=lookup
    graph=dict(run_tutor_step(1,'不会',0))
    p=original.fallback_plan(graph,a);q=migrated.fallback_plan(graph,b)
    c=original.AgentToolContext('数学','综合题','题干','4',[], '不会',1,['一次方程'],a)
    d=migrated.AgentToolContext('数学','综合题','题干','4',[], '不会',1,['一次方程'],b)
    assert (await original.execute_agent_tool(object(),p,c)).model_dump()==(await migrated.execute_agent_tool(cards,q,d)).model_dump()
asyncio.run(compare())
print('original agent parity passed')
"""


def test_agent_rules_match_original_in_isolated_reference_process():
    rows = [
        [
            {
                "id": "m1",
                "knowledge_point": "一次方程",
                "mastery_score": 0.4,
                "confidence": 0.8,
                "forgetting_risk": 0.7,
            }
        ],
        [
            {
                "id": "c1",
                "code": "sign",
                "label": "符号",
                "probability": 0.6,
                "status": "active",
                "successful_strategy": "micro_activity",
            }
        ],
        [
            {
                "id": "u1",
                "entity_type": "mastery",
                "entity_key": "一次方程",
                "old_value": 0.2,
                "new_value": 0.4,
                "reason": "练习完成",
            }
        ],
        [{"id": "r1", "reason": "定期回顾", "interval_days": 3}],
    ]
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", REFERENCE],
        input=json.dumps(rows),
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "PYTHONPATH": str(root / "backend")
            + os.pathsep
            + str(root / "backend-algorithms"),
        },
        check=True,
    )
    assert "original agent parity passed" in result.stdout


def test_dialogue_computation_fallback_keeps_stage_and_uses_supplied_cards(tmp_path):
    secret = "dialogue-compute-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    context = {
        "student_message": "我不会",
        "subject": "数学",
        "question_type": "综合题",
        "question_text": "解方程",
        "final_answer": "x=4",
        "reference_steps": ["2x=8", "x=4"],
        "turn_count": 1,
        "knowledge_points": ["一次方程"],
        "recent_turns": [{"role": "user", "content": "我不会"}],
    }
    headers = {"Authorization": "Bearer " + secret}
    with TestClient(app) as client:
        prepared = client.post(
            "/v1/compute",
            headers=headers,
            json={"operation": "tutor_dialogue_prepare", "dialogue_context": context},
        )
        assert prepared.status_code == 200, prepared.text
        preparation = prepared.json()["result"]
        assert (
            preparation["planner_status"] == "fallback"
            and preparation["plan"]["tool_name"] == "knowledge_search"
        )
        response = client.post(
            "/v1/compute",
            headers=headers,
            json={
                "operation": "tutor_dialogue_finish",
                "dialogue_context": context,
                "dialogue_preparation": preparation,
                "dialogue_cards": [
                    {
                        "code": "EQ",
                        "name": "一次方程",
                        "content": {"definition": "两边同做相同运算"},
                    }
                ],
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert "知识卡 · 一次方程" in result["reply"]
        assert result["agent"]["verification"]["status"] == "verified"
        assert result["graph"]["mastery_proven"] is False
        assert app.state.provider is None


def test_dialogue_preserves_complete_long_formula_and_conditions(tmp_path, monkeypatch):
    explanation = (
        "先确认题目给出的条件。" * 12
        + r"当 $x\ne 0$ 时，$\frac{2x+3}{x}=2+\frac{3}{x}$。"
        + "请写出你认为等价的下一步，并说明分母不能为零的原因。"
    )

    async def guidance(*args, **kwargs):
        return explanation

    monkeypatch.setattr("dialogue_compute.generate_tutor_guidance", guidance)
    secret = "complete-content-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    headers = {"Authorization": "Bearer " + secret}
    context = {"student_message": "我想检查这一步", "turn_count": 1}
    with TestClient(app) as client:
        preparation = client.post(
            "/v1/compute",
            headers=headers,
            json={"operation": "tutor_dialogue_prepare", "dialogue_context": context},
        ).json()["result"]
        result = client.post(
            "/v1/compute",
            headers=headers,
            json={
                "operation": "tutor_dialogue_finish",
                "dialogue_context": context,
                "dialogue_preparation": preparation,
            },
        )
        assert result.status_code == 200
        assert explanation in result.json()["result"]["reply"]
