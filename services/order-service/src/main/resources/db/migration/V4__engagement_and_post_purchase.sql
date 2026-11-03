-- Phase 2: reviews UGC, wishlists, back-in-stock alerts, saved-for-later, address book, returns, gift cards.

ALTER TABLE reviews ADD COLUMN helpful_count INT NOT NULL DEFAULT 0;
ALTER TABLE reviews ADD COLUMN verified BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE reviews ADD COLUMN customer_id UUID NULL REFERENCES customers(id);
ALTER TABLE reviews ADD COLUMN size_purchased TEXT;
ALTER TABLE reviews ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
UPDATE reviews SET helpful_count = (id * 7) % 23;

CREATE TABLE review_votes (
  review_id  BIGINT NOT NULL REFERENCES reviews(id),
  voter      TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (review_id, voter)
);

CREATE TABLE wishlists (
  id          UUID PRIMARY KEY,
  customer_id UUID NULL UNIQUE REFERENCES customers(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE wishlist_items (
  wishlist_id UUID NOT NULL REFERENCES wishlists(id),
  product_id  TEXT NOT NULL REFERENCES products(id),
  color       TEXT,
  added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (wishlist_id, product_id)
);

CREATE TABLE stock_notifications (
  id          BIGSERIAL PRIMARY KEY,
  sku         TEXT NOT NULL REFERENCES skus(sku),
  email       TEXT NOT NULL,
  customer_id UUID NULL REFERENCES customers(id),
  status      TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SENT')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (sku, email)
);

CREATE TABLE bag_saved_items (
  bag_id    UUID NOT NULL REFERENCES bags(id),
  sku       TEXT NOT NULL REFERENCES skus(sku),
  saved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (bag_id, sku)
);

CREATE TABLE customer_addresses (
  id          UUID PRIMARY KEY,
  customer_id UUID NOT NULL REFERENCES customers(id),
  label       TEXT,
  name        TEXT NOT NULL,
  line1       TEXT NOT NULL,
  line2       TEXT,
  city        TEXT NOT NULL,
  state       TEXT NOT NULL,
  zip         TEXT NOT NULL,
  phone       TEXT,
  is_default  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX customer_addresses_customer_idx ON customer_addresses(customer_id);

CREATE SEQUENCE return_number_seq START 700001;

CREATE TABLE returns (
  id            UUID PRIMARY KEY,
  return_number TEXT NOT NULL UNIQUE,
  order_id      UUID NOT NULL REFERENCES orders(id),
  status        TEXT NOT NULL DEFAULT 'REQUESTED' CHECK (status IN ('REQUESTED', 'RECEIVED', 'REFUNDED')),
  method        TEXT NOT NULL CHECK (method IN ('MAIL', 'STORE')),
  refund_cents  INT NOT NULL CHECK (refund_cents >= 0),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX returns_order_idx ON returns(order_id);

CREATE TABLE return_lines (
  return_id     UUID NOT NULL REFERENCES returns(id),
  line_no       INT NOT NULL,
  quantity      INT NOT NULL CHECK (quantity > 0),
  reason        TEXT NOT NULL,
  refund_cents  INT NOT NULL,
  PRIMARY KEY (return_id, line_no)
);

CREATE TABLE gift_cards (
  number        TEXT PRIMARY KEY,
  pin_hash      TEXT NOT NULL,
  balance_cents INT NOT NULL CHECK (balance_cents >= 0),
  expires_on    DATE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Demo cards (PINs are documented in docs/OTTERSHOPS.md; SHA-256 of number:pin, fine for a fictional balance check).
INSERT INTO gift_cards (number, pin_hash, balance_cents, expires_on) VALUES
  ('6006491234567890', encode(sha256('6006491234567890:1234'::bytea), 'hex'), 5000, NULL),
  ('6006490000000000', encode(sha256('6006490000000000:0000'::bytea), 'hex'), 0, NULL),
  ('6006495555444433', encode(sha256('6006495555444433:4321'::bytea), 'hex'), 12575, '2027-12-31');
