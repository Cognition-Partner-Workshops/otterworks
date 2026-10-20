package example.claimshub.maps;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.Map;

import org.springframework.stereotype.Component;
import org.w3c.dom.Element;

/**
 * BizTalk map {@code InsertClaim_to_TriageFacts}: {@code usp_InsertClaim} to the {@code TriageFacts} rules fact
 * document. The two C# scripting functoids are {@link #computeReserve} and {@link #daysBetween}; every other field is
 * a straight link.
 */
@Component
public class InsertClaimToTriageFactsTransformer {

    static final String SOURCE_NS = "http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo";
    static final String TARGET_NS = "http://schemas.thistlecombe.example/claims/triage";

    private static final Map<String, BigDecimal> RESERVE_FACTORS = Map.of(
            "COLL", new BigDecimal("1.10"),
            "COMP", new BigDecimal("1.00"),
            "GLAS", new BigDecimal("0.85"),
            "THFT", new BigDecimal("1.25"),
            "FIRE", new BigDecimal("1.40"),
            "WATR", new BigDecimal("1.30"),
            "WIND", new BigDecimal("1.15"),
            "LIAB", new BigDecimal("1.60"));
    private static final BigDecimal DEFAULT_FACTOR = new BigDecimal("1.00");
    private static final BigDecimal INJURY_LOADING = new BigDecimal("0.35");

    public byte[] transform(byte[] source) {
        Element claim = FlatTargetXml.parseRoot(source, SOURCE_NS, "usp_InsertClaim");
        return FlatTargetXml.document("ns0", TARGET_NS, "TriageFacts")
                .element("ClaimNumber", FlatTargetXml.text(claim, "ClaimNumber"))
                .element("LossCause", FlatTargetXml.text(claim, "LossCause"))
                .element("EstimatedAmount", FlatTargetXml.text(claim, "EstimatedAmount"))
                .element("ReserveEstimate", computeReserve(FlatTargetXml.text(claim, "EstimatedAmount"),
                        FlatTargetXml.text(claim, "LossCause"), FlatTargetXml.text(claim, "InjuryFlag")))
                .element("ReportDelayDays", daysBetween(FlatTargetXml.text(claim, "LossDate"), FlatTargetXml.text(claim, "ReportedDate")))
                .element("PolicyAgeDaysAtLoss", daysBetween(FlatTargetXml.text(claim, "PolicyEffectiveDate"), FlatTargetXml.text(claim, "LossDate")))
                .element("InjuryFlag", FlatTargetXml.text(claim, "InjuryFlag"))
                .element("PriorFraudFlag", FlatTargetXml.text(claim, "PriorFraudFlag"))
                .element("InForceAtLoss", FlatTargetXml.text(claim, "InForceAtLoss"))
                .element("NetExposure", FlatTargetXml.text(claim, "NetExposure"))
                .toBytes();
    }

    /** C# {@code ComputeReserve}: estimate times the loss-cause factor (+0.35 with injury), .NET {@code Math.Round} to cents. */
    static String computeReserve(String estimatedAmount, String lossCause, String injuryFlag) {
        BigDecimal estimate = Money.parse(estimatedAmount);
        BigDecimal factor = RESERVE_FACTORS.getOrDefault(lossCause, DEFAULT_FACTOR);
        if ("true".equals(injuryFlag)) {
            factor = factor.add(INJURY_LOADING);
        }
        return Money.format(estimate.multiply(factor).setScale(2, RoundingMode.HALF_EVEN));
    }

    /** C# {@code DaysBetween}: whole days from {@code fromDate} to {@code toDate} (yyyy-MM-dd), negative when earlier. */
    static String daysBetween(String fromDate, String toDate) {
        return Long.toString(ChronoUnit.DAYS.between(LocalDate.parse(fromDate.strip()), LocalDate.parse(toDate.strip())));
    }
}
