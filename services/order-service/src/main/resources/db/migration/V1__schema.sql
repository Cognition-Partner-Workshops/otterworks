CREATE TABLE collections (
  slug         TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  department   TEXT,
  description  TEXT,
  hero_image   TEXT,
  sort_order   INT NOT NULL DEFAULT 0
);

CREATE TABLE products (
  id                    TEXT PRIMARY KEY,
  name                  TEXT NOT NULL,
  label                 TEXT,
  department            TEXT NOT NULL,
  category              TEXT NOT NULL,
  fit                   TEXT,
  description           TEXT,
  details               TEXT,
  materials             TEXT,
  list_price_cents      INT NOT NULL CHECK (list_price_cents > 0),
  markdown_price_cents  INT NULL CHECK (markdown_price_cents IS NULL OR markdown_price_cents > 0),
  rating                NUMERIC(2,1) NOT NULL DEFAULT 0,
  review_count          INT NOT NULL DEFAULT 0,
  is_new                BOOLEAN NOT NULL DEFAULT FALSE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE product_collections (
  product_id       TEXT NOT NULL REFERENCES products(id),
  collection_slug  TEXT NOT NULL REFERENCES collections(slug),
  PRIMARY KEY (product_id, collection_slug)
);

CREATE TABLE product_images (
  product_id  TEXT NOT NULL REFERENCES products(id),
  position    INT NOT NULL,
  url         TEXT NOT NULL,
  alt         TEXT,
  color       TEXT,
  PRIMARY KEY (product_id, position)
);

CREATE TABLE skus (
  sku           TEXT PRIMARY KEY,
  product_id    TEXT NOT NULL REFERENCES products(id),
  color         TEXT NOT NULL,
  color_hex     TEXT NOT NULL,
  color_family  TEXT NOT NULL,
  size          TEXT NOT NULL,
  size_order    INT NOT NULL,
  stock         INT NOT NULL CHECK (stock >= 0)
);
CREATE INDEX skus_product_idx ON skus(product_id);

CREATE TABLE product_links (
  product_id  TEXT NOT NULL REFERENCES products(id),
  related_id  TEXT NOT NULL REFERENCES products(id),
  position    INT NOT NULL,
  PRIMARY KEY (product_id, related_id)
);

CREATE TABLE reviews (
  id          BIGSERIAL PRIMARY KEY,
  product_id  TEXT NOT NULL REFERENCES products(id),
  author      TEXT NOT NULL,
  location    TEXT,
  rating      INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  title       TEXT,
  body        TEXT,
  fit_note    TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX reviews_product_idx ON reviews(product_id);

CREATE TABLE stores (
  id                  TEXT PRIMARY KEY,
  name                TEXT NOT NULL,
  address             TEXT NOT NULL,
  city                TEXT NOT NULL,
  state               TEXT NOT NULL,
  zip                 TEXT NOT NULL,
  phone               TEXT,
  hours               TEXT,
  latitude            DOUBLE PRECISION,
  longitude           DOUBLE PRECISION,
  pickup_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
  pickup_ready_hours  INT NOT NULL DEFAULT 2
);

CREATE TABLE customers (
  id              UUID PRIMARY KEY,
  email           TEXT NOT NULL UNIQUE,
  password_hash   TEXT NOT NULL,
  first_name      TEXT,
  last_name       TEXT,
  rewards_points  INT NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customer_sessions (
  token        TEXT PRIMARY KEY,
  customer_id  UUID NOT NULL REFERENCES customers(id),
  expires_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE bags (
  id           UUID PRIMARY KEY,
  customer_id  UUID NULL REFERENCES customers(id),
  promo_code   TEXT,
  status       TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CONVERTED')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX bags_customer_idx ON bags(customer_id) WHERE status = 'OPEN';

CREATE TABLE bag_items (
  bag_id    UUID NOT NULL REFERENCES bags(id),
  sku       TEXT NOT NULL REFERENCES skus(sku),
  quantity  INT NOT NULL CHECK (quantity > 0),
  added_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (bag_id, sku)
);

CREATE SEQUENCE order_number_seq START 100001;
CREATE SEQUENCE invoice_number_seq START 500001;

CREATE TABLE orders (
  id                 UUID PRIMARY KEY,
  order_number       TEXT NOT NULL UNIQUE,
  customer_id        UUID NULL REFERENCES customers(id),
  email              TEXT NOT NULL,
  status             TEXT NOT NULL,
  fulfillment        TEXT NOT NULL CHECK (fulfillment IN ('SHIP', 'PICKUP')),
  shipping_method    TEXT,
  store_id           TEXT NULL REFERENCES stores(id),
  ship_name          TEXT,
  ship_line1         TEXT,
  ship_line2         TEXT,
  ship_city          TEXT,
  ship_state         TEXT,
  ship_zip           TEXT,
  phone              TEXT,
  promo_code         TEXT,
  subtotal_cents     INT NOT NULL,
  discount_cents     INT NOT NULL,
  shipping_cents     INT NOT NULL,
  fees_cents         INT NOT NULL,
  tax_cents          INT NOT NULL,
  total_cents        INT NOT NULL,
  payment_provider   TEXT NOT NULL,
  payment_reference  TEXT NOT NULL,
  card_brand         TEXT,
  card_last4         TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX orders_customer_idx ON orders(customer_id);
CREATE INDEX orders_updated_idx ON orders(updated_at);

CREATE TABLE order_lines (
  order_id          UUID NOT NULL REFERENCES orders(id),
  line_no           INT NOT NULL,
  sku               TEXT NOT NULL,
  product_id        TEXT NOT NULL,
  name              TEXT NOT NULL,
  color             TEXT,
  size              TEXT,
  image_url         TEXT,
  quantity          INT NOT NULL CHECK (quantity > 0),
  unit_list_cents   INT NOT NULL,
  unit_price_cents  INT NOT NULL,
  discount_cents    INT NOT NULL,
  line_total_cents  INT NOT NULL,
  PRIMARY KEY (order_id, line_no)
);

CREATE TABLE order_fees (
  order_id      UUID NOT NULL REFERENCES orders(id),
  code          TEXT NOT NULL,
  label         TEXT NOT NULL,
  amount_cents  INT NOT NULL,
  PRIMARY KEY (order_id, code)
);

CREATE TABLE invoices (
  invoice_number  TEXT PRIMARY KEY,
  order_id        UUID NOT NULL UNIQUE REFERENCES orders(id),
  issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  total_cents     INT NOT NULL
);
