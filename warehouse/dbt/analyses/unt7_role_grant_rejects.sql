{% set subject = var('unt7_subject', 'production') %}
{% if subject == 'production' %}
  {{ pc_content_role_grant(source('unt7_pc_src','ROLE_GRANT'), rejects=true) }}
{% elif subject in ['seeded','dup_key'] %}
  {{ pc_content_role_grant(source('unt7_fixture',subject.upper() ~ '_SOURCE'), rejects=true, raw_input=true) }}
{% else %}
  {{ exceptions.raise_compiler_error('Unknown UNT-7 subject') }}
{% endif %}
