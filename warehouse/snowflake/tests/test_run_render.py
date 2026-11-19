import pytest

from warehouse.run_config import RunConfig


@pytest.mark.parametrize('token', ['sfx1119', 'sfx2220', 'sfx-d1110', 'sfx-d1110-alice'])
@pytest.mark.parametrize('legacy', ['1110', '2222'])
def test_render_replaces_original_matches_only(token, legacy):
    config = RunConfig(token)
    source = ('__RUN_TOKEN__ __RUN_DATABASE__ __BEFORE_NAMESPACE__ __AFTER_NAMESPACE__ '
              f'sfx-d{legacy} sfx-d{legacy}-before sfx-d{legacy}-after '
              f'SFX_D{legacy} SFX_D{legacy}_AFTER')
    assert config.render(source).split() == [
        config.token, config.database, config.before_namespace, config.after_namespace,
        config.token, config.before_namespace, config.after_namespace, config.database, config.database]


@pytest.mark.parametrize('value', [None, 0, [], {}, '', '__UNKNOWN__', 'unrelated text'])
def test_render_preserves_empty_non_text_and_unrelated_values(value):
    assert RunConfig('sfx-d1110-alice').render(value) == value
