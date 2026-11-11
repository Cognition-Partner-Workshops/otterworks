{% macro pc_relation_comment() %}
    comment on {{ 'view' if model.config.materialized == 'view' else 'table' }} {{ this }}
    is 'run_token=sfx-d1110 expires=2026-11-24'
{% endmacro %}

{% macro pc_finalize_comments(results) %}
    {% if execute %}
        {% for result in results if result.status == 'success' %}
            {% set node = result.node %}
            {% if node.resource_type == 'model' and node.fqn[1] == 'pc'
                  and node.config.materialized in ['table', 'view', 'incremental'] %}
                {% set relation = adapter.get_relation(database=node.database, schema=node.schema, identifier=node.alias) %}
                {% if relation is not none %}
                    {% do run_query("comment on " ~ ('view' if relation.is_view else 'table') ~ ' ' ~ relation
                        ~ " is 'run_token=sfx-d1110 expires=2026-11-24'") %}
                {% endif %}
            {% endif %}
        {% endfor %}
    {% endif %}
    {{ return('') }}
{% endmacro %}
