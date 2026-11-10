{% set subject=var('unt8_subject','production') %}
{% if subject not in ['production','seeded','dup_key'] %}
{{ exceptions.raise_compiler_error('Unknown UNT-8 subject') }}
{% endif %}
{{ pc_content_team_member(source('unt8_pc_src','TEAM_MEMBER') if subject == 'production' else source('unt8_fixture',subject | upper ~ '_SOURCE'), rejects=true, raw_input=subject != 'production') }}
