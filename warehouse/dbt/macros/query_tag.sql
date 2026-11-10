{% macro sfx_query_tag() %}
    {% set tag = fromjson(env_var('SFX_QUERY_TAG')) %}
    {% if tag.workload == 'transform' and tag.phase == var('phase', 'dbt')
          and tag.run_token == var('run_token') %}
        {{ return(env_var('SFX_QUERY_TAG')) }}
    {% endif %}
    {% do tag.update({'workload': 'transform', 'phase': var('phase', 'dbt'),
                      'run_token': var('run_token')}) %}
    {{ return(tojson(tag)) }}
{% endmacro %}

{% macro set_query_tag() %}
    {% set original = get_current_query_tag() %}
    {% do run_query("alter session set query_tag = '" ~ sfx_query_tag() | replace("'", "''") ~ "'") %}
    {{ return(original) }}
{% endmacro %}

{% macro unset_query_tag(original_query_tag) %}
    {% if original_query_tag is not none %}
        {% do run_query("alter session set query_tag = '" ~ original_query_tag | replace("'", "''") ~ "'") %}
    {% else %}
        {% do run_query("alter session unset query_tag") %}
    {% endif %}
{% endmacro %}
