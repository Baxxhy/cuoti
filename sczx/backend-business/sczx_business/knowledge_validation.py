"""Validate the complete knowledge catalog before set operations or database writes."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from .retrieval import normalize

Identifier = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=40)]
Name = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=160)]
Alias = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100)]

class KnowledgeInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: Identifier
    name: Name
    aliases: list[Alias] = Field(default_factory=list, max_length=20)
    prerequisites: list[Identifier] = Field(default_factory=list, max_length=100)

class KnowledgeCatalogInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    points: list[KnowledgeInput] = Field(min_length=1, max_length=500)

def validate_catalog(points):
    ids=[p['id'] for p in points]
    if len(set(ids)) != len(ids):raise ValueError('知识点ID重复。')
    names=[normalize(p['name']) for p in points]
    if len(set(names)) != len(names):raise ValueError('知识点正式名称重复。')
    occupied=set(names)
    for point in points:
        for alias in point['aliases']:
            key=normalize(alias)
            if key in occupied:raise ValueError('知识点别名重复或与正式名称冲突。')
            occupied.add(key)
    graph={p['id']:p['prerequisites'] for p in points}
    for values in graph.values():
        if len(set(values)) != len(values):raise ValueError('前置关系重复。')
        if any(v not in graph for v in values):raise ValueError('前置知识点不存在。')
    active=set();done=set()
    def visit(node):
        if node in active:raise ValueError('知识前置关系存在循环。')
        if node in done:return
        active.add(node)
        for prior in graph[node]:visit(prior)
        active.remove(node);done.add(node)
    for node in graph:visit(node)
