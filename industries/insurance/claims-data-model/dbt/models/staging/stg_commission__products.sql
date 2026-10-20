select product_code, product_name, line_of_business
  from {{ source('commission', 'products') }}
