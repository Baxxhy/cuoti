"""Audit UI call sites separately from validation references; never equate them."""

import ast
import json
import re
from pathlib import Path


def normalized(path):
    path = re.sub(r"\$\{[^}]*\}", "{}", path)
    path = re.sub(r"\{[^}]*\}", "{}", path).split("?")[0]
    path = path.removeprefix("/api/v1")
    if path.endswith("{}") and not path.endswith("/{}"):
        path = path[:-2]
    return path


def py_path(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            item.value if isinstance(item, ast.Constant) else "{}"
            for item in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return py_path(node.left) + py_path(node.right)
    return ""


def collect(root):
    calls = []
    methods = {
        "getData": "GET",
        "postData": "POST",
        "patchData": "PATCH",
        "deleteData": "DELETE",
        "uploadFile": "POST",
    }
    for path in sorted((root / "frontend/src").rglob("*")):
        if path.suffix not in {".vue", ".js", ".ts"}:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r'\b(getData|postData|patchData|deleteData|uploadFile)\(\s*([\x27"`])(.*?)\2',
            text,
            re.DOTALL,
        ):
            if match[3].startswith("/"):
                calls.append(
                    (
                        methods[match[1]],
                        normalized(match[3]),
                        f"{path.relative_to(root).as_posix()}:{text.count(chr(10), 0, match.start()) + 1}",
                        "ui",
                    )
                )
        for match in re.finditer(r'upload-url="([^"]+)"', text):
            calls.append(
                (
                    "POST",
                    normalized(match[1]),
                    f"{path.relative_to(root).as_posix()}:{text.count(chr(10), 0, match.start()) + 1}",
                    "ui",
                )
            )
    for folder in ("scripts", "backend/tests", "backend/app"):
        for path in sorted((root / folder).glob("*.py")):
            if path.name == Path(__file__).name:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            decorators = {
                id(decorator)
                for definition in ast.walk(tree)
                if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef))
                for decorator in definition.decorator_list
            }
            for node in ast.walk(tree):
                if (
                    not isinstance(node, ast.Call)
                    or not node.args
                    or id(node) in decorators
                ):
                    continue
                name = node.func.attr if isinstance(node.func, ast.Attribute) else ""
                method = name.upper()
                if method not in {"GET", "POST", "PATCH", "DELETE", "PUT"}:
                    continue
                value = py_path(node.args[0])
                if value.startswith("/"):
                    calls.append(
                        (
                            method,
                            normalized(value),
                            f"{path.relative_to(root).as_posix()}:{node.lineno}",
                            "validation" if folder != "backend/app" else "internal",
                        )
                    )
    return calls


def audit(root):
    routes = json.loads((root / "docs/cangjie/routes.json").read_text(encoding="utf-8"))
    retired_path = root / "docs/cangjie/routes_retired.json"
    retired = (
        json.loads(retired_path.read_text(encoding="utf-8"))
        if retired_path.exists()
        else []
    )
    calls = collect(root)
    result = []
    for row in routes + retired:
        evidence = {
            kind: sorted(
                {
                    location
                    for method, path, location, found_kind in calls
                    if found_kind == kind
                    and method == row["method"]
                    and path == normalized(row["path"])
                }
            )
            for kind in ("ui", "validation", "internal")
        }
        result.append({**row, "usage_evidence": evidence})
    return result


NOTES = {
    "PATCH /api/v1/auth/me": (
        "independent_api",
        "账号改名能力；当前资料页没有编辑入口，不属于学生主页面必需接口。",
    ),
    "GET /api/v1/system/health": (
        "existing_support",
        "既有检查脚本依赖；本轮不做运维、不扩展或部署该能力。",
    ),
    "GET /api/v1/system/voice": (
        "independent_api",
        "独立语音验收脚本查询能力状态；学生页面未接语音，不算页面已使用。",
    ),
    "PATCH /api/v1/questions/{question_id}": (
        "independent_api",
        "题干/元数据编辑与学习结果失效；脚本通过 HTTP 调用，页面确认目前走 confirm。",
    ),
    "POST /api/v1/questions/{question_id}/draft": (
        "independent_api",
        "保存未确认内容；有功能测试，当前页面直接 confirm，不宣称页面自动保存。",
    ),
    "POST /api/v1/questions/{question_id}/ocr": (
        "independent_api",
        "同步识别工具入口；当前页面使用异步 crop/reprocess，独立脚本仍调用。",
    ),
    "POST /api/v1/questions/{question_id}/student-work": (
        "independent_api",
        "独立追加作答版本、步骤并使旧结果失效；用于功能验证，当前页面走 confirm。",
    ),
    "GET /api/v1/questions/{question_id}/diagnosis": (
        "independent_api",
        "单独读取诊断证据；当前页面从题目详情聚合读取，独立返回契约仍有验证。",
    ),
    "POST /api/v1/tutor/sessions/{session_id}/teach-back": (
        "script_workflow",
        "functional_flow.py、verify_agent_branches.py 的分步教学脚本仍调用；学生页面走 activity/answer。",
    ),
    "POST /api/v1/tutor/sessions/{session_id}/variant": (
        "script_workflow",
        "脚本分步生成练习；页面会话读取与作答路径自动补题，不能把内部生成函数调用算成直接调用此 HTTP 路由。",
    ),
    "POST /api/v1/variants/{variant_id}/attempt": (
        "script_workflow",
        "分步教学脚本提交练习并写入认知证据；页面走 activity/answer。",
    ),
    "POST /api/v1/tutor/sessions/{session_id}/finish": (
        "script_workflow",
        "functional_flow.py、smoke_demo.py 结束教学；页面由活动流程自动结束。",
    ),
    "GET /api/v1/visualizations/types": (
        "independent_api",
        "可视化验收脚本读取类型目录，页面未调用，不计为页面必需。",
    ),
    "GET /api/v1/visualizations/{visualization_id}": (
        "independent_api",
        "独立按 ID 读取图形规范；页面使用会话可视化接口，脚本验证此独立能力。",
    ),
    "GET /api/v1/knowledge/cards": (
        "independent_api",
        "共享知识卡搜索能力，由知识库验收脚本调用；当前知识页展示题目已有分析，不调用此目录。",
    ),
    "GET /api/v1/knowledge/cards/{code}": (
        "independent_api",
        "知识卡独立详情和先修关系，由知识库验收脚本调用；当前页面未接入口。",
    ),
    "POST /api/v1/voice/transcribe": (
        "independent_api",
        "语音验收脚本使用的独立专业能力；当前学生页面没有语音入口。保留算法，不追加页面。",
    ),
    "POST /api/v1/voice/synthesize": (
        "independent_api",
        "语音验收脚本使用的独立专业能力；当前学生页面没有语音入口。保留算法，不追加页面。",
    ),
    "DELETE /api/v1/teachers/classes/{class_id}/students/{student_id}": (
        "independent_api",
        "教师移除成员并撤销班级报告/计划权限，有 HTTP 验证；当前班级页面只提供添加入口。",
    ),
    "POST /api/v1/teachers/reviews/{task_id}/revoke": (
        "independent_api",
        "教师撤销已发布复核及其学习效果，有独立语义；当前页面未放撤销按钮，不等同 decision。",
    ),
    "POST /api/v1/teachers/reviews/{task_id}/regrade": (
        "independent_api",
        "教师重新判定既有复核，有独立语义；当前页面未提供按钮，不等同首次 decision。",
    ),
    "POST /api/v1/teachers/reviews/{task_id}/transfer": (
        "independent_api",
        "教师转交复核任务，有独立权限与审计语义；当前页面未提供按钮。",
    ),
    "GET /api/v1/students/teacher-feedback": (
        "independent_api",
        "独立反馈历史，返回结果与任务；首页/作业只返回相应摘要，不是完全相同的响应。",
    ),
    "GET /api/v1/papers/{paper_id}/download": (
        "script_workflow",
        "试卷验收脚本按 kind 下载最新导出；页面实际消费 exports[].url 中的 /reports 签名链接，不调用此接口。",
    ),
    "GET /api/v1/practice/questions/{question_id}/images/{image_index}": (
        "returned_media",
        "练习推荐响应产生签名图片 URL，练习页面 image 消费；属于必要资源接口。",
    ),
}


def publish(root, check=False):
    rows = audit(root)
    # Resolve dynamic calls through their actual call sites and checked helpers.
    overrides = {
        "GET /api/v1/questions": (
            "frontend/src/pages/problem/list.vue",
            "getData(questionSearchURL(filters))",
        ),
        "POST /api/v1/jobs/{job_id}/retry": (
            "frontend/src/pages/ocr/ocr.vue",
            "/retry",
        ),
        "GET /api/v1/teachers/reviews": (
            "frontend/src/pages/teacher/reviews.vue",
            "/teachers/reviews${",
        ),
    }
    for row in rows:
        key = row["method"] + " " + row["path"]
        if key in overrides:
            filename, needle = overrides[key]
            lines = (root / filename).read_text(encoding="utf-8").splitlines()
            hits = [
                f"{filename}:{i + 1}" for i, line in enumerate(lines) if needle in line
            ]
            assert hits, key
            row["usage_evidence"]["ui"].extend(hits)
            if key == "GET /api/v1/questions":
                helper = "frontend/src/utils/learning.js"
                helper_lines = (root / helper).read_text(encoding="utf-8").splitlines()
                helper_hits = [
                    f"{helper}:{i + 1}"
                    for i, line in enumerate(helper_lines)
                    if "return `/questions${query" in line
                ]
                assert helper_hits, "questionSearchURL must still target /questions"
                row["usage_evidence"]["ui"].extend(helper_hits)
        if row.get("status") == "retired":
            assert not row["usage_evidence"]["ui"], key
            row["usage_class"] = "removed"
            row["usage_reason"] = row["retirement_reason"]
        elif row["usage_evidence"]["ui"]:
            row["usage_class"] = "ui"
            row["usage_reason"] = "现有页面或组件存在直接 API 调用；保留。"
        else:
            assert key in NOTES, ("requires manual review", key)
            row["usage_class"], row["usage_reason"] = NOTES[key]
    assert len(rows) == 103
    assert len({(r["method"], r["path"]) for r in rows}) == 103
    summary = {
        kind: sum(r["usage_class"] == kind for r in rows)
        for kind in sorted({r["usage_class"] for r in rows})
    }
    result = {
        "baseline_routes": 103,
        "active_routes": sum(r["usage_class"] != "removed" for r in rows),
        "categories": summary,
        "routes": rows,
    }
    target = root / "docs/cangjie/routes_usage.json"
    if check:
        assert json.loads(target.read_text(encoding="utf-8")) == result, (
            "Route audit is stale; regenerate after reviewing changes"
        )
    else:
        target.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        lines = [
            "# 103 条接口的实际用途审计",
            "",
            "按现有页面、动态请求、响应中的资源 URL、脚本调用及接口行为逐条检查。没有页面入口不等于没有能力；测试引用不计为产品实际调用。未使用的别名、空操作及废弃入口已删除。",
            "",
            f"不做运维或部署，不新增页面凑接口使用量。学生学习与作业下发、作答、判题、反馈所需接口保留。仓颉接口迁移状态：{sum(row.get('status') == 'verified' for row in rows)}/{result['active_routes']} verified；实现和验证入口见 routes.json，验收范围见 FINAL_ACCEPTANCE.md。",
            "",
            f"原清单 103 条，删除 {summary.get('removed', 0)} 条，保留 {result['active_routes']} 条。分类：`{summary}`。",
            "",
            "| 方法 | 路径 | 分类 | 实际用途/处理 | 页面调用证据 |",
            "|---|---|---|---|---|",
        ]
        for row in rows:
            lines.append(
                "| "
                + row["method"]
                + " | `"
                + row["path"]
                + "` | "
                + row["usage_class"]
                + " | "
                + row["usage_reason"]
                + " | "
                + "、".join(row["usage_evidence"]["ui"])
                + " |"
            )
        (root / "docs/cangjie/ROUTE_USAGE.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "routes"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    import sys

    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    root = Path(args[0]) if args else Path(__file__).resolve().parents[1]
    publish(root, check="--check" in sys.argv)
