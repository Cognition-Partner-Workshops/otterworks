{% macro governance_identifier(value) %}
  {% set parts = value.split('.') %}
  {% if parts | length != 3 %}
    {{ exceptions.raise_compiler_error('Governance policy requires database.schema.name: ' ~ value) }}
  {% endif %}
  {{ return(adapter.quote(parts[0]) ~ '.' ~ adapter.quote(parts[1]) ~ '.' ~ adapter.quote(parts[2])) }}
{% endmacro %}

{% macro reapply_governance(results=none) %}
  {% if not execute %}{{ return('') }}{% endif %}
  {% set token = env_var('SNOWFLAKE_RUN_TOKEN', 'sfx-d1110') | replace("'", "''") %}
  {% set nodes = [] %}
  {% if results is not none %}
    {% for result in results if result.node.resource_type in ['model', 'seed', 'snapshot'] and result.status == 'success' %}
      {% do nodes.append(result.node) %}
    {% endfor %}
  {% else %}
    {% for node in graph.nodes.values() if node.resource_type in ['model', 'seed', 'snapshot'] %}
      {% do nodes.append(node) %}
    {% endfor %}
  {% endif %}
  {% for node in nodes if node.config.materialized != 'ephemeral' %}
    {% set relation = adapter.get_relation(database=node.database, schema=node.schema, identifier=node.alias) %}
    {% if relation is not none %}
      {% set kind = 'view' if relation.is_view else 'table' %}
      {% set tag = adapter.quote(node.database) ~ '.GOVERNANCE.SFX_RUN' %}
      {% do run_query('alter ' ~ kind ~ ' ' ~ relation ~ ' set tag ' ~ tag ~ " = '" ~ token ~ "'") %}
      {% do run_query('comment on ' ~ kind ~ ' ' ~ relation ~ " is '" ~ token ~ ' ' ~ ((node.description or node.name) | replace("'", "''")) ~ "'") %}
      {% set policies = var('governance_policies', {}).get(node.name, {}) %}
      {% for column, tags in policies.get('column_tags', {}).items() %}
        {% for tag_name, value in tags.items() %}
          {% do run_query('alter ' ~ kind ~ ' ' ~ relation ~ ' modify column ' ~ adapter.quote(column) ~ ' set tag ' ~ governance_identifier(tag_name) ~ " = '" ~ (value | replace("'", "''")) ~ "'") %}
        {% endfor %}
      {% endfor %}
      {% for masking in policies.get('masking', []) %}
        {% do run_query('alter ' ~ kind ~ ' ' ~ relation ~ ' modify column ' ~ adapter.quote(masking['column']) ~ ' set masking policy ' ~ governance_identifier(masking['policy']) ~ ' force') %}
      {% endfor %}
      {% set row_policy = policies.get('row_access') %}
      {% if row_policy %}
        {% set refs = run_query("select policy_db || '.' || policy_schema || '.' || policy_name from table(" ~ adapter.quote(node.database) ~ ".information_schema.policy_references(ref_entity_name => '" ~ (relation | string | replace("'", "''")) ~ "', ref_entity_domain => '" ~ kind | upper ~ "')) where policy_kind = 'ROW_ACCESS_POLICY'") %}
        {% if refs.rows | length > 0 and refs.rows[0][0] | upper != row_policy['policy'] | upper %}
          {{ exceptions.raise_compiler_error('Different row access policy already attached to ' ~ node.name) }}
        {% endif %}
        {% if refs.rows | length == 0 %}
          {% set columns = [] %}
          {% for column in row_policy['columns'] %}{% do columns.append(adapter.quote(column)) %}{% endfor %}
          {% do run_query('alter ' ~ kind ~ ' ' ~ relation ~ ' add row access policy ' ~ governance_identifier(row_policy['policy']) ~ ' on (' ~ columns | join(', ') ~ ')') %}
        {% endif %}
      {% endif %}
      {% do log('governance reapplied: ' ~ relation, info=True) %}
    {% endif %}
  {% endfor %}
  {{ return('') }}
{% endmacro %}
