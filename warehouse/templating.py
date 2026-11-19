"""Separate browser rendering from the repository's dbt SQL/metadata test harnesses.

dbt_environment renders reviewed SQL macros, JSON query tags and YAML scalar
values, never HTML. Escaping quotes, comparison operators or ampersands would
corrupt those formats. Callers supply dbt context functions and must validate SQL
identifiers/bind values separately; this environment is not a SQL sanitizer.
Use html_environment for browser output, and mark only trusted fragments with
markupsafe.Markup. Both environments reject missing template variables.
"""

from jinja2 import Environment, StrictUndefined, select_autoescape
from jinja2.sandbox import SandboxedEnvironment


def dbt_environment(*, extensions=()):
    # Reviewed dbt SQL/JSON/YAML, not HTML; escaping would change executable SQL/data.
    return Environment(autoescape=False, undefined=StrictUndefined, extensions=extensions)  # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2


def html_environment():
    return SandboxedEnvironment(
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
    )
