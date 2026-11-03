-- Over-bump jeans belong on the denim collection page alongside the rest of the jeans range.
UPDATE product_collections
SET collection_slug = 'denim'
WHERE collection_slug = 'maternity'
  AND product_id IN (SELECT id FROM products WHERE name ILIKE '%jeans%');
