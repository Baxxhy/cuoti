import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1] / 'schema'
_TYPES = {**json.loads((_ROOT / 'column_types.json').read_text()), **json.loads((_ROOT / 'task_column_types.json').read_text())}


def row_json(table, row):
    types = _TYPES[table]
    result = {}
    for key, value in row.items():
        kind = types[key]
        if value is None:
            result[key] = None
        elif kind == 'json':
            result[key] = json.loads(value)
        elif kind == 'bool':
            result[key] = value != '0'
        elif kind == 'int':
            result[key] = int(value)
        elif kind == 'float':
            result[key] = float(value)
        elif kind == 'datetime':
            result[key] = value.replace(' ', 'T') + '+00:00'
        else:
            result[key] = value
    if table == 'questions' and 'title' in row and 'question_text' in row:
        title, text = row['title'], row['question_text']
        if title and text != title and text.startswith(title) and ('$' in title or '\\' in title):
            result['title'] = text
    return result
