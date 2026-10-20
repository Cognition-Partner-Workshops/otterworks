-- The examiner's question, asked by both roles: what does this login see
-- about the claimant on each claim?
SELECT c.claim_number, p.claimant_name, p.tax_id, p.date_of_birth, p.phone, p.address, p.bank_account
  FROM claims_api.claim c
  JOIN claims_api.claimant p USING (claimant_id)
 ORDER BY c.claim_number;
