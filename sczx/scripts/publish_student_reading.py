#!/usr/bin/env python3
"""Publish explicit student reading as a new version; never change existing tasks."""
import argparse
import copy
import json
from pathlib import Path
import httpx

REVISION = 'student-reading-20261111-v1'


def publish(base, accounts_path):
    accounts = json.loads(Path(accounts_path).read_text())
    admin = next(a for a in accounts if a['role'] == 'admin')
    report = []
    with httpx.Client(base_url=base, timeout=30) as client:
        client.post('/api/auth/login', json={k: admin[k] for k in ('username', 'password')}).raise_for_status()
        courses = client.get('/api/curriculum/courses'); courses.raise_for_status()
        for course in courses.json():
            for unit in course['units']:
                for lesson in unit['lessons']:
                    current = lesson.get('published')
                    if not current or current.get('studentReadingRevision') == REVISION:
                        continue
                    data = copy.deepcopy(current)
                    for block in data['blocks']:
                        # Canonical published text remains the reference; no keyword deletion.
                        block.setdefault('studentContent', block['content'])
                        block.setdefault('studentTitle', block['title'])
                    data['studentReadingRevision'] = REVISION
                    path = '/api/curriculum/lessons/' + lesson['id']
                    # Refuse to overwrite an administrator's unfinished revision.
                    if lesson.get('status') != 'published':
                        raise RuntimeError('课时有未完成修订：' + lesson['id'])
                    for suffix, method, payload in [('/revise', 'POST', None), ('', 'PUT', {'data': data}),
                                                      ('/verify', 'POST', None), ('/review', 'POST', None),
                                                      ('/publish', 'POST', None)]:
                        response = client.request(method, path + suffix, **({'json': payload} if payload else {}))
                        response.raise_for_status()
                    latest = client.get(path); latest.raise_for_status()
                    new = latest.json()['published']
                    report.append({'lessonId': lesson['id'], 'beforeVersion': current['versionId'],
                                   'afterVersion': new['versionId'], 'version': new['version']})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--accounts', required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.base, args.accounts), ensure_ascii=False, indent=2))
