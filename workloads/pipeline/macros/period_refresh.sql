{% materialization period_refresh, adapter='snowflake' %}
  {% set relation = this.incorporate(type='table') %}
  {% call statement('main') %}
    call {{ this.database }}.APP.REFRESH_{{ this.identifier | upper }}()
  {% endcall %}
  {{ return({'relations': [relation]}) }}
{% endmaterialization %}
