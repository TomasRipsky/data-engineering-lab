{#
    dev/prod: one dataset per layer (staging, intermediate, marts), created by Terraform.
    ci: every layer prefixed with the per-PR dataset name, e.g. ci_pr_12_marts.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set layer = (custom_schema_name or 'staging') | trim -%}
    {%- if target.name == 'ci' -%}
        {{ target.schema }}_{{ layer }}
    {%- else -%}
        {{ layer }}
    {%- endif -%}
{%- endmacro %}
