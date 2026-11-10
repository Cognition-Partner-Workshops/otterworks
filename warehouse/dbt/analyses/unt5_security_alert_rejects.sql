{% set subject = var('unt5_subject', 'production') %}
{% if subject == 'production' %}
  {% set input = source('unt5_pc_src','SECURITY_ALERT') %}
{% elif subject in ['seeded','dup_within_route'] %}
  {% set input = source('unt5_fixture',subject.upper() ~ '_SOURCE') %}
{% else %}
  {{ exceptions.raise_compiler_error('Unknown UNT-5 subject') }}
{% endif %}
{{ pc_audit_security_alert(input, rejects=true) }}
