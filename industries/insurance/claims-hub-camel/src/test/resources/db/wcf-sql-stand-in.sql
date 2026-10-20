-- PostgreSQL 16 stand-in for the two WCF-SQL ports FnolIntake talks to (ESTATE.md, Bindings):
--   sp_PolicyAdmin_PolicyInq_WcfSql  solicit-response  usp_GetPolicyAsOf  -> usp_get_policy_as_of(PolicyInqRq) returns PolicyInqRs
--   sp_ClaimsDb_InsertClaim_WcfSql   one-way           usp_InsertClaim    -> usp_insert_claim(usp_InsertClaim)
-- Like the typed procedures, both take and return the XML message itself.

create table policy_version (
    policy_number      text          not null,
    valid_from         date          not null,
    valid_to           date          not null default 'infinity',
    status_cd          text          not null,
    lob_cd             text          not null,
    effective_dt       date          not null,
    expiration_dt      date          not null,
    deductible_amt     numeric(12,2) not null,
    coverage_limit_amt numeric(12,2) not null,
    insured_party_id   text          not null,
    primary key (policy_number, valid_from),
    check (valid_from < valid_to)
);

create table policy_coverage (
    policy_number text          not null,
    valid_from    date          not null,
    seq           int           not null,
    coverage_cd   text          not null,
    limit_amt     numeric(12,2) not null,
    primary key (policy_number, valid_from, seq),
    foreign key (policy_number, valid_from) references policy_version (policy_number, valid_from)
);

create table claim (
    claim_number          text primary key,
    policy_number         text          not null,
    policy_status         text          not null,
    policy_effective_date date          not null,
    line_of_business      text          not null,
    insured_party_id      text          not null,
    claimant_name         text          not null,
    claimant_tax_id_masked text,
    loss_date             date          not null,
    reported_date         date          not null,
    loss_cause            text          not null,
    loss_description      text          not null,
    estimated_amount      numeric(12,2) not null,
    deductible            numeric(12,2) not null,
    coverage_limit        numeric(12,2) not null,
    net_exposure          numeric(12,2) not null,
    injury_flag           boolean       not null,
    prior_fraud_flag      boolean       not null,
    in_force_at_loss      boolean       not null,
    agency_id             text          not null,
    triage_outcome        text          not null,
    inserted_at           timestamptz   not null default now()
);

-- The policy as it stood on PolicyInqRq/AsOfDt; null when no version covers that date.
create function usp_get_policy_as_of(rq xml) returns xml language sql stable as $$
    with req as (
        select (xpath('/*/RqUID/text()', rq))[1]::text          as rquid,
               (xpath('/*/PolicyNumber/text()', rq))[1]::text   as policy_number,
               ((xpath('/*/AsOfDt/text()', rq))[1]::text)::date as as_of
    )
    select xmlelement(name "ns0:PolicyInqRs",
               xmlattributes('http://schemas.thistlecombe.example/acord/policy' as "xmlns:ns0"),
               xmlelement(name "RqUID", req.rquid),
               xmlelement(name "PolicyNumber", v.policy_number),
               xmlelement(name "PolicyStatusCd", v.status_cd),
               xmlelement(name "LOBCd", v.lob_cd),
               xmlelement(name "EffectiveDt", v.effective_dt),
               xmlelement(name "ExpirationDt", v.expiration_dt),
               xmlelement(name "DeductibleAmt", v.deductible_amt),
               xmlelement(name "CoverageLimitAmt", v.coverage_limit_amt),
               xmlelement(name "InsuredPartyId", v.insured_party_id),
               (select xmlagg(xmlelement(name "Coverage",
                                  xmlelement(name "CoverageCd", c.coverage_cd),
                                  xmlelement(name "LimitAmt", c.limit_amt)) order by c.seq)
                  from policy_coverage c
                 where c.policy_number = v.policy_number and c.valid_from = v.valid_from))
      from req
      join policy_version v
        on v.policy_number = req.policy_number
       and req.as_of >= v.valid_from and req.as_of < v.valid_to
$$;

-- The claims system's primary key on claim_number is what rejects a duplicate FNOL that arrives after the correction window.
create function usp_insert_claim(doc xml) returns text language sql as $$
    insert into claim (claim_number, policy_number, policy_status, policy_effective_date, line_of_business,
                       insured_party_id, claimant_name, claimant_tax_id_masked, loss_date, reported_date,
                       loss_cause, loss_description, estimated_amount, deductible, coverage_limit, net_exposure,
                       injury_flag, prior_fraud_flag, in_force_at_loss, agency_id, triage_outcome)
    select x.* from xmltable('/*' passing doc columns
        claim_number text path 'ClaimNumber',
        policy_number text path 'PolicyNumber',
        policy_status text path 'PolicyStatus',
        policy_effective_date date path 'PolicyEffectiveDate',
        line_of_business text path 'LineOfBusiness',
        insured_party_id text path 'InsuredPartyId',
        claimant_name text path 'ClaimantName',
        claimant_tax_id_masked text path 'ClaimantTaxIdMasked',
        loss_date date path 'LossDate',
        reported_date date path 'ReportedDate',
        loss_cause text path 'LossCause',
        loss_description text path 'LossDescription',
        estimated_amount numeric(12,2) path 'EstimatedAmount',
        deductible numeric(12,2) path 'Deductible',
        coverage_limit numeric(12,2) path 'CoverageLimit',
        net_exposure numeric(12,2) path 'NetExposure',
        injury_flag boolean path 'InjuryFlag',
        prior_fraud_flag boolean path 'PriorFraudFlag',
        in_force_at_loss boolean path 'InForceAtLoss',
        agency_id text path 'AgencyId',
        triage_outcome text path 'TriageOutcome') x
    returning claim_number
$$;
