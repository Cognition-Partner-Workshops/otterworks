import pytest
from jinja2 import DictLoader, UndefinedError
from markupsafe import Markup

from warehouse.templating import dbt_environment, html_environment


def test_html_escapes_untrusted_values_and_preserves_explicit_trusted_fragments():
    template = html_environment().from_string('{{ value }}{{ trusted }}')
    assert template.render(value='<script>alert("x")</script>', trusted=Markup('<b>ok</b>')) == (
        '&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt;<b>ok</b>')


@pytest.mark.parametrize('name', ['page.html', 'page.xml', 'page'])
def test_named_html_templates_escape(name):
    environment = html_environment()
    environment.loader = DictLoader({name: '{{ value }}'})
    assert environment.get_template(name).render(value='<script>') == '&lt;script&gt;'


def test_dbt_preserves_non_html_bytes():
    source = 'select {{ expression }} where x < 2 and y = \'a&b\'\n'
    assert dbt_environment().from_string(source).render(expression="'a<b&c'") == (
        "select 'a<b&c' where x < 2 and y = 'a&b'")


@pytest.mark.parametrize('factory', [dbt_environment, html_environment])
def test_empty_templates_and_undefined_values(factory):
    environment = factory()
    assert environment.from_string('').render() == ''
    with pytest.raises(UndefinedError):
        environment.from_string('{{ missing }}').render()
