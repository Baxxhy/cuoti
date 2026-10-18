"""Export existing public knowledge content without loading ORM or business config."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    tree = ast.parse((ROOT / "scripts/seed_knowledge.py").read_text())
    scope = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"TOPICS", "GRADE_TOPICS"}
    }
    card = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "card_content"
    )
    base_expression = compile(
        ast.Expression(body=card.body[0].value), "public-card-content", "eval"
    )
    curriculum = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Dict)
        and any(
            isinstance(target, ast.Name) and target.id == "content"
            for target in node.targets
        )
    )
    content_expression = compile(
        ast.Expression(body=curriculum), "curriculum-content", "eval"
    )
    cards, relations = [], []
    for subject, topics in scope["TOPICS"].items():
        prefix = "math" if subject == "数学" else subject.lower()
        for index, (slug, name, chapter, formula, visualization) in enumerate(topics):
            cards.append(
                {
                    "code": f"{prefix}.{slug}",
                    "subject": subject,
                    "name": name,
                    "content": eval(
                        base_expression,
                        {
                            "subject": subject,
                            "index": index,
                            "name": name,
                            "chapter": chapter,
                            "formula": formula,
                            "visualization": visualization,
                            "previous": topics[index - 1][1] if index else None,
                            "following": topics[index + 1][1]
                            if index + 1 < len(topics)
                            else None,
                        },
                    ),
                }
            )
            if index:
                relations.append(
                    {
                        "source": f"{prefix}.{slug}",
                        "target": f"{prefix}.{topics[index - 1][0]}",
                    }
                )
    for subject, grades in scope["GRADE_TOPICS"].items():
        for grade, topics in grades.items():
            for index, name in enumerate(topics):
                content = eval(
                    content_expression,
                    {
                        "subject": subject,
                        "grade": grade,
                        "topics": topics,
                        "index": index,
                        "name": name,
                    },
                )
                cards.append(
                    {
                        "code": f"curr.{subject}.{grade}.{index + 1}",
                        "subject": subject,
                        "name": name,
                        "content": content,
                    }
                )
    return {"cards": cards, "relations": relations}


def main():
    target = ROOT / "backend-cangjie/schema/knowledge_seed.json"
    target.write_text(json.dumps(snapshot(), ensure_ascii=False, indent=2) + "\n")
    print("Public knowledge snapshot generated")


if __name__ == "__main__":
    main()
