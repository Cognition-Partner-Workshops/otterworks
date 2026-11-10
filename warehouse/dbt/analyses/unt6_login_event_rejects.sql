{% set subject = var('unt6_subject', 'production') %}
{% if subject == 'production' %}
  {{ pc_content_login_event(source('unt6_pc_src','LOGIN_EVENT'), rejects=true) }}
{% elif subject in ['seeded','dup_within_route'] %}
  {{ pc_content_login_event(source('unt6_fixture',subject.upper() ~ '_SOURCE'), rejects=true, raw_input=true) }}
{% else %}
  {{ exceptions.raise_compiler_error('Unknown UNT-6 subject') }}
{% endif %}
