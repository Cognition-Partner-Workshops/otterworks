-- The ledger side of sp_ClaimsDb_LedgerPost_WcfSql. dbo.usp_PostClaimPayment takes the
-- ClaimsDb_LedgerPost document; the reversal is the same document sent to the reversal action,
-- which negates it. Each call is one row; nothing is updated in place.
create schema if not exists ledger;

create table ledger.claim_payment_entry (
    entry_id          bigint generated always as identity primary key,
    instruction_id    varchar(16)    not null,
    claim_number      varchar(15)    not null,
    vendor_reference  varchar(32)    not null,
    entry_type        varchar(8)     not null check (entry_type in ('POST', 'REVERSAL')),
    document          text           not null,
    value_date        date           not null,
    currency          char(3)        not null,
    indemnity_amount  numeric(15, 2) not null,
    expense_amount    numeric(15, 2) not null,
    salvage_credit    numeric(15, 2) not null,
    net_amount        numeric(15, 2) not null,
    line_count        integer        not null,
    recorded_at       timestamptz    not null default now()
);

create unique index claim_payment_entry_once on ledger.claim_payment_entry (instruction_id, entry_type);

create function ledger.document_value(document xml, field text) returns text
language sql immutable as $$
    select (xpath('/ns0:usp_PostClaimPayment/' || field || '/text()', document,
        array[array['ns0', 'http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo']]))[1]::text
$$;

create function ledger.record_entry(document_text text, kind text, sign integer) returns bigint
language plpgsql as $$
declare
    doc xml := document_text::xml;
    id bigint;
begin
    insert into ledger.claim_payment_entry (instruction_id, claim_number, vendor_reference, entry_type, document,
            value_date, currency, indemnity_amount, expense_amount, salvage_credit, net_amount, line_count)
    values (ledger.document_value(doc, 'InstructionId'), ledger.document_value(doc, 'ClaimNumber'),
            ledger.document_value(doc, 'VendorReference'), kind, document_text,
            ledger.document_value(doc, 'ValueDate')::date, ledger.document_value(doc, 'Currency'),
            sign * ledger.document_value(doc, 'IndemnityAmount')::numeric,
            sign * ledger.document_value(doc, 'ExpenseAmount')::numeric,
            sign * ledger.document_value(doc, 'SalvageCredit')::numeric,
            sign * ledger.document_value(doc, 'NetAmount')::numeric,
            ledger.document_value(doc, 'LineCount')::integer)
    returning entry_id into id;
    return id;
end
$$;

-- dbo.usp_PostClaimPayment
create function ledger.post_claim_payment(document_text text) returns bigint
language sql as $$ select ledger.record_entry(document_text, 'POST', 1) $$;

-- The reversal action. Only a post can be reversed, with the document it was posted with, and only once;
-- a compensation that finds nothing to reverse (the post never committed) does nothing and returns null.
create function ledger.reverse_claim_payment(document_text text) returns bigint
language plpgsql as $$
declare
    instruction text := ledger.document_value(document_text::xml, 'InstructionId');
    posted text;
begin
    select document into posted from ledger.claim_payment_entry where instruction_id = instruction and entry_type = 'POST';
    if posted is null then
        return null;
    end if;
    if posted <> document_text then
        raise exception 'reversal document for % differs from the posted document', instruction;
    end if;
    if exists (select 1 from ledger.claim_payment_entry where instruction_id = instruction and entry_type = 'REVERSAL') then
        return null;
    end if;
    return ledger.record_entry(document_text, 'REVERSAL', -1);
end
$$;
