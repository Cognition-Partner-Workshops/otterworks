CREATE TABLE products (product_id NUMBER(8) PRIMARY KEY, name VARCHAR2(80) NOT NULL);
CREATE TABLE accounts (
 account_id NUMBER(15) PRIMARY KEY,
 holder_name VARCHAR2(100) NOT NULL,
 address VARCHAR2(160) NOT NULL,
 product_id NUMBER(8) REFERENCES products(product_id),
 balance NUMBER(15,2) NOT NULL,
 opened_at DATE NOT NULL
);
CREATE TABLE seed_version (version VARCHAR2(64) PRIMARY KEY);
