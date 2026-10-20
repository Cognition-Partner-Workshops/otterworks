package example.claimshub.maps;

import static example.claimshub.maps.AggregateEnvelope.exists;
import static example.claimshub.maps.AggregateEnvelope.text;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;

import org.w3c.dom.Element;

/**
 * BizTalk map {@code Claim_PolicyInqRs_to_InsertClaim}: the canonical claim (part 0) and the policy
 * inquiry response (part 1) become the {@code usp_InsertClaim} typed-procedure call.
 *
 * <p>{@code NetExposure} is the estimate capped at the coverage limit, less the deductible, floored at
 * zero. {@code InForceAtLoss} needs status {@code Active} and a loss date inside the effective and
 * expiration dates, both inclusive. Amounts are {@link BigDecimal}; {@code format-number(x, '0.00')}
 * rounds half to even. A missing or non-numeric amount behaves like XPath {@code NaN}: comparisons are
 * false and it is written as {@code NaN}.
 */
public final class ClaimPolicyInqRsToInsertClaimTransformer {

    static final String CLAIM_NS = "http://schemas.thistlecombe.example/canonical/claim";
    static final String POLICY_NS = "http://schemas.thistlecombe.example/acord/policy";
    static final String ROOT_OPEN = "<ns0:usp_InsertClaim xmlns:ns0=\"http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo\""
            + " xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">";
    static final String ROOT_CLOSE = "</ns0:usp_InsertClaim>";

    public byte[] transform(byte[] source) {
        AggregateEnvelope envelope = AggregateEnvelope.parse(source);
        Element c = envelope.part(0, CLAIM_NS, "Claim");
        Element p = envelope.part(1, POLICY_NS, "PolicyInqRs");

        BigDecimal est = number(text(c, "Loss", "EstimatedAmount"));
        BigDecimal limit = number(text(p, "CoverageLimitAmt"));
        BigDecimal ded = number(text(p, "DeductibleAmt"));
        BigDecimal capped = lessThan(est, limit) ? est : limit;
        BigDecimal cappedLessDeductible = capped == null || ded == null ? null : capped.subtract(ded);
        BigDecimal net = cappedLessDeductible != null && cappedLessDeductible.signum() > 0 ? cappedLessDeductible : BigDecimal.ZERO;

        BigDecimal lossNum = number(text(c, "Loss", "LossDate").replace("-", ""));
        BigDecimal effNum = number(text(p, "EffectiveDt").replace("-", ""));
        BigDecimal expNum = number(text(p, "ExpirationDt").replace("-", ""));
        boolean inForce = "Active".equals(text(p, "PolicyStatusCd"))
                && !lessThan(lossNum, effNum) && lossNum != null && effNum != null
                && !lessThan(expNum, lossNum) && expNum != null;

        SaxonXmlWriter w = new SaxonXmlWriter().raw(ROOT_OPEN)
                .element("ClaimNumber", text(c, "ClaimNumber"))
                .element("PolicyNumber", text(p, "PolicyNumber"))
                .element("PolicyStatus", text(p, "PolicyStatusCd"))
                .element("PolicyEffectiveDate", text(p, "EffectiveDt"))
                .element("LineOfBusiness", text(p, "LOBCd"))
                .element("InsuredPartyId", text(p, "InsuredPartyId"))
                .element("ClaimantName", text(c, "Claimant", "FullName"));
        if (exists(c, "Claimant", "TaxIdMasked")) {
            w.element("ClaimantTaxIdMasked", text(c, "Claimant", "TaxIdMasked"));
        } else {
            w.raw("<ClaimantTaxIdMasked xsi:nil=\"true\"/>");
        }
        w.element("LossDate", text(c, "Loss", "LossDate"))
                .element("ReportedDate", text(c, "Loss", "ReportedDate"))
                .element("LossCause", text(c, "Loss", "CauseCode"))
                .element("LossDescription", text(c, "Loss", "Description"))
                .element("EstimatedAmount", money(est))
                .element("Deductible", money(ded))
                .element("CoverageLimit", money(limit))
                .element("NetExposure", money(net))
                .element("InjuryFlag", text(c, "Loss", "Injury"))
                .element("PriorFraudFlag", text(c, "Claimant", "PriorFraudFlag"))
                .element("InForceAtLoss", inForce ? "true" : "false")
                .element("AgencyId", text(c, "Agency", "Id"))
                .raw("<TriageOutcome xsi:nil=\"true\"/>")
                .raw(ROOT_CLOSE);
        return w.toString().getBytes(StandardCharsets.UTF_8);
    }

    /** XPath {@code number()}: null stands for NaN. */
    static BigDecimal number(String s) {
        String t = s.strip();
        if (t.isEmpty() || !t.matches("[+-]?(\\d+(\\.\\d*)?|\\.\\d+)")) {
            return null;
        }
        return new BigDecimal(t);
    }

    private static boolean lessThan(BigDecimal a, BigDecimal b) {
        return a != null && b != null && a.compareTo(b) < 0;
    }

    static String money(BigDecimal amount) {
        return amount == null ? "NaN" : amount.setScale(2, RoundingMode.HALF_EVEN).toPlainString();
    }
}
