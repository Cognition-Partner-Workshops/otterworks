import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import assess
import deliverables


@pytest.fixture(scope='module')
def estate():
    return assess.build()


def test_graph_covers_mermaid_nodes_and_links(estate):
    graph = deliverables.graph(estate, assess.uid)
    ids = {n['id'] for n in graph['nodes']}
    assert len(ids) == len(graph['nodes'])
    assert {r['id'] for r in estate['objects'] + estate['consumers']} <= ids
    assert {assess.uid('feed:' + path) for path in estate['feeds']} <= ids
    assert all(a in ids and b in ids for a, b in graph['links'])
    assert graph['links'] == [[assess.uid(a) if a.startswith('feed:') else a, b] for a, b in estate['links']]
    assert {n['layer'] for n in graph['nodes']} == set(range(7))


def test_offline_html_escapes_script_content():
    data = dict(objects=[], artifacts=[], consumers=[], external_relations=[], links=[], feeds=['</script><script>alert(1)</script>'])
    html = deliverables.lineage_html(data, assess.uid)
    payload = re.search(r'<script id="lineage-data" type="application/json">(.*?)</script>', html, re.S)[1]
    assert json.loads(payload)['nodes'][0]['name'] == data['feeds'][0]
    assert '</script>' not in payload
    assert 'src=' not in html and 'fetch(' not in html
    data['feeds'] = []
    assert deliverables.graph(data, assess.uid)['nodes'] == []


def test_wave_plan_scope_evidence_and_reviews(estate):
    plan = deliverables.wave_plan(estate)
    for wave in range(1, 5):
        assert f"## Wave {wave}\n\nObjects: {sum(r['wave'] == wave for r in estate['objects'])}" in plan
    for row in estate['objects']:
        assert f"**{row['name']}**" in plan
        assert row['owner'] in plan
        if row['target_type'] == 'retire':
            assert deliverables.retirement(row) in plan
    assert 'Review before cutover' in plan
    assert 'ModuleNotFoundError' in plan
    assert 'last QueryID/principal=' in plan
    assert 'last run=' in plan


def test_empty_wave_plan_and_invalid_retirement():
    plan = deliverables.wave_plan(dict(objects=[], dependencies=[], stale=[]))
    assert plan.count('Objects: 0') == 4
    assert 'None.' in plan
    with pytest.raises(KeyError):
        deliverables.retirement({'system': 'spark'})
