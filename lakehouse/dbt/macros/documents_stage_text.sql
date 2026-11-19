{% macro documents_stage_text(column) -%}
case when length({{ column }}) > 200
     then cast(raise_error('documents staging text exceeds VARCHAR(200)') as string)
     else {{ column }} end
{%- endmacro %}
