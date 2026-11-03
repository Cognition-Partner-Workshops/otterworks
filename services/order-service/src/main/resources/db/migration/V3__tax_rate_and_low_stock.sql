-- Keep the exact rate charged so invoices don't re-derive it from rounded cents.
ALTER TABLE orders ADD COLUMN tax_rate NUMERIC(5,2);

-- Give a handful of products a nearly sold-out size run so PLP "Low stock" badges appear.
WITH picked AS (
  SELECT product_id
  FROM skus
  JOIN products p ON p.id = skus.product_id
  WHERE p.department IN ('women', 'men', 'kids', 'denim', 'activewear')
  GROUP BY product_id
  HAVING SUM(stock) > 10
  ORDER BY md5(product_id)
  LIMIT 12
), ranked AS (
  SELECT s.sku, row_number() OVER (PARTITION BY s.product_id ORDER BY s.color, s.size_order) AS rn
  FROM skus s JOIN picked USING (product_id)
)
UPDATE skus SET stock = CASE WHEN ranked.rn <= 3 THEN 3 ELSE 0 END
FROM ranked WHERE skus.sku = ranked.sku;
