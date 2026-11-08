"""小规模教学案例的 BM25 检索；中文二元组，无向量和模型依赖。"""
from collections import Counter
import math
import re
import unicodedata


def tokenize(text):
    text = unicodedata.normalize('NFKC', str(text)).lower()
    tokens = []
    for part in re.findall(r'[\u3400-\u9fff]+|[a-z]+|\d+(?:\.\d+)?|[=+*/^<>-]', text):
        if re.fullmatch(r'[\u3400-\u9fff]+', part):
            tokens.extend(part[i:i + 2] for i in range(len(part) - 1))
            if len(part) == 1: tokens.append(part)
        else:
            tokens.append(part)
    return tokens


def search(query, documents, limit=8):
    """返回正分匹配；空查询、空库和零匹配不返回占位案例。"""
    terms = set(tokenize(query))
    if not terms or not documents: return []
    counts = [Counter(tokenize(f"{d.get('title', '')} {d.get('title', '')} {d.get('content', '')} {d.get('retrievalText', '')}")) for d in documents]
    lengths = [sum(count.values()) for count in counts]
    average = sum(lengths) / len(lengths) or 1
    frequencies = {term: sum(term in count for count in counts) for term in terms}
    ranked = []
    for document, count, length in zip(documents, counts, lengths):
        score = 0.0
        for term in terms:
            frequency = count.get(term, 0)
            if not frequency: continue
            inverse = math.log1p((len(documents) - frequencies[term] + .5) / (frequencies[term] + .5))
            score += inverse * frequency * 2.5 / (frequency + 1.5 * (.25 + .75 * length / average))
        if score > 0:
            ranked.append({**document, 'score': round(score, 6), 'bm25Score': round(score, 6)})
    return sorted(ranked, key=lambda item: (-item['score'], str(item['id'])))[:limit]


def published_documents(db):
    from sqlalchemy import select
    from .models import TeachingCase
    from .library import current_case
    import json
    results = []
    for case in db.scalars(select(TeachingCase).where(TeachingCase.status == 'published').order_by(TeachingCase.id)).all():
        data = current_case(db, case.id)
        if data: results.append({**data, 'retrievalText': json.dumps(data.get('experience', {}), ensure_ascii=False)})
    return results
