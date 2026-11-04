{#
  Use the schema named in the model config exactly as written (e.g. "silver"),
  instead of dbt's default "<target schema>_<custom schema>" (e.g. "silver_silver").
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
