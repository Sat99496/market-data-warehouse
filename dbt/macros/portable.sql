{#
  Small cross-database helpers so the same models run on DuckDB (local + CI)
  and on Databricks (Azure) without changes.
#}

{# One row per calendar day between two date expressions, as column `date_day`. #}
{% macro date_series(start_date, end_date) -%}
    {{ return(adapter.dispatch('date_series', 'market_dw')(start_date, end_date)) }}
{%- endmacro %}

{% macro default__date_series(start_date, end_date) -%}
    select cast(unnest(generate_series(cast({{ start_date }} as date), cast({{ end_date }} as date), interval 1 day)) as date) as date_day
{%- endmacro %}

{% macro databricks__date_series(start_date, end_date) -%}
    select explode(sequence(cast({{ start_date }} as date), cast({{ end_date }} as date), interval 1 day)) as date_day
{%- endmacro %}


{# Carry the last non-null value forward (e.g. Friday's FX rate over the weekend). #}
{% macro forward_fill(column, partition_by, order_by) -%}
    {{ return(adapter.dispatch('forward_fill', 'market_dw')(column, partition_by, order_by)) }}
{%- endmacro %}

{% macro default__forward_fill(column, partition_by, order_by) -%}
    last_value({{ column }} ignore nulls) over (
        partition by {{ partition_by }} order by {{ order_by }}
        rows between unbounded preceding and current row)
{%- endmacro %}

{% macro databricks__forward_fill(column, partition_by, order_by) -%}
    last_value({{ column }}, true) over (
        partition by {{ partition_by }} order by {{ order_by }}
        rows between unbounded preceding and current row)
{%- endmacro %}


{# Date helpers: integer YYYYMMDD key, month and day names, weekend flag. #}
{% macro date_key(col) -%}{{ return(adapter.dispatch('date_key', 'market_dw')(col)) }}{%- endmacro %}
{% macro default__date_key(col) -%}cast(strftime({{ col }}, '%Y%m%d') as integer){%- endmacro %}
{% macro databricks__date_key(col) -%}cast(date_format({{ col }}, 'yyyyMMdd') as int){%- endmacro %}

{% macro month_name(col) -%}{{ return(adapter.dispatch('month_name', 'market_dw')(col)) }}{%- endmacro %}
{% macro default__month_name(col) -%}strftime({{ col }}, '%B'){%- endmacro %}
{% macro databricks__month_name(col) -%}date_format({{ col }}, 'MMMM'){%- endmacro %}

{% macro day_name(col) -%}{{ return(adapter.dispatch('day_name', 'market_dw')(col)) }}{%- endmacro %}
{% macro default__day_name(col) -%}strftime({{ col }}, '%A'){%- endmacro %}
{% macro databricks__day_name(col) -%}date_format({{ col }}, 'EEEE'){%- endmacro %}

{# ISO day of week, Monday = 1 ... Sunday = 7, the same on both engines. #}
{% macro iso_day_of_week(col) -%}{{ return(adapter.dispatch('iso_day_of_week', 'market_dw')(col)) }}{%- endmacro %}
{% macro default__iso_day_of_week(col) -%}isodow({{ col }}){%- endmacro %}
{% macro databricks__iso_day_of_week(col) -%}weekday({{ col }}) + 1{%- endmacro %}


{# Deterministic surrogate key from one or more columns. #}
{% macro surrogate_key(columns) -%}
    md5(concat_ws('|', {% for c in columns %}coalesce(cast({{ c }} as varchar), '~null~'){% if not loop.last %}, {% endif %}{% endfor %}))
{%- endmacro %}
