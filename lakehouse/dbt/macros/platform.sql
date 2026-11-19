{% test dbql_catalog_key(model) %}
select lower(rtrim(databasename)), lower(rtrim(tablename))
from {{ model }}
group by lower(rtrim(databasename)), lower(rtrim(tablename))
having count(*) > 1
{% endtest %}
