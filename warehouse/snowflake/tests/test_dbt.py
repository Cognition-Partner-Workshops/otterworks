
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import importlib.util
from pathlib import Path

import yaml
import pytest

ROOT = Path(__file__).resolve().parents[2]
DBT = ROOT / "dbt"


@pytest.mark.parametrize('platform,name', [('win32', 'dbt.exe'), ('linux', 'dbt')])
def test_dbt_executable_is_adjacent_and_platform_specific(monkeypatch, platform, name):
    monkeypatch.syspath_prepend(str(ROOT / 'snowflake'))
    spec = importlib.util.spec_from_file_location('run_dbt', ROOT / 'snowflake/run_dbt.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.sys, 'platform', platform)
    assert module.dbt_executable() == Path(module.sys.executable).with_name(name)


def helper(filename):
    spec = importlib.util.spec_from_file_location("renderer", DBT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sources_match_spec():
    renderer = helper("render_sources.py")
    assert _run_render(renderer.TARGET.read_text()) == renderer.render()
    spec = yaml.safe_load(_run_render(renderer.SPEC.read_text()))
    sources = yaml.safe_load(_run_render(renderer.TARGET.read_text()))["sources"]
    assert {s["name"]: {t["name"]: [c["name"] for c in t["columns"]]
                       for t in s["tables"]} for s in sources} == {
        area: {table: list(columns) for table, columns in tables.items()}
        for area, tables in spec.items()
    }


def test_billing_matches_spec():
    for filename, content in helper("render_billing.py").render().items():
        assert _run_render((DBT / "models/staging/billing" / filename).read_text()) == content


def test_profile_uses_secret_safe_pem():
    profile = yaml.safe_load(_run_render((DBT / "profiles.yml").read_text()))
    output = profile["sfx_warehouse"]["outputs"]["dev"]
    assert output["private_key"] == "{{ env_var('DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY') }}"
    assert "private_key_path" not in output
    assert output["query_tag"] == "{{ env_var('SFX_QUERY_TAG') }}"
