{% macro generate_alias_name(custom_alias_name=none, node=none) -%}
    {% if modules.re.match('^pc_(billing|content|audit)__[a-z0-9_]+$', node.name) %}
        {{ node.name.split('__', 1)[1] | upper }}
    {% elif custom_alias_name %}
        {{ custom_alias_name | trim }}
    {% else %}
        {{ node.name }}
    {% endif %}
{%- endmacro %}
