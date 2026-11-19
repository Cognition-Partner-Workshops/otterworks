DROP TABLE IF EXISTS crm.service_cases;
DROP TABLE IF EXISTS crm.subscription_snapshots;
DROP TABLE IF EXISTS crm.contacts;
CREATE TABLE crm.contacts (
 contact_id UUID PRIMARY KEY,
 full_name TEXT NOT NULL,
 address TEXT NOT NULL,
 credit DOUBLE PRECISION NOT NULL
);
CREATE TABLE crm.service_cases (
 case_id UUID PRIMARY KEY,
 contact_id UUID NOT NULL REFERENCES crm.contacts(contact_id),
 subject TEXT NOT NULL,
 opened_at TIMESTAMP NOT NULL
);
CREATE TABLE crm.subscription_snapshots (
 contact_id UUID PRIMARY KEY REFERENCES crm.contacts(contact_id),
 status TEXT NOT NULL
);
