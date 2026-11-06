"""Same fixture used by original Cangjie LearningJourneyTest."""
import json
from pathlib import Path
import pytest
from sczx_api.journey import build,time_key,journey_time
from sczx_api.practice_context import equivalent

_CASES=json.loads((Path(__file__).parent/'fixtures/journey_parity.json').read_text())


@pytest.mark.parametrize('case',_CASES,ids=[c['name'] for c in _CASES])
def test_original_journey_projection(case):
    assert equivalent(build(case['input'],case['now']),case['expected'])


def test_time_precision_preserves_equal_time_order_and_local_day_boundary():
    assert time_key('2026-10-16 08:00:00')==time_key('2026-10-16T08:00:00.000000Z')
    assert journey_time('2026-10-16T08:00:00.1Z')=='2026-10-16T08:00:00.100000+00:00'
