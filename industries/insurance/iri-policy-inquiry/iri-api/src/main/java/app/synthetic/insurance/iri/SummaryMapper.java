package app.synthetic.insurance.iri;

import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.Map;
import java.util.Set;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/** Maps an annuity_policy row to PolicySummary per lineage/lineage.yaml (operation summary). */
@Component
public class SummaryMapper {
    static final Map<String, String> POLICY_STATUS = Map.of("IF", "ACTIVE", "PI", "PENDINGISSUED",
            "LP", "LAPSED", "SR", "SURRENDERED", "TM", "TERMINATED");
    // S-02: DP has no IRI policyStatus value.
    static final Set<String> SIGNOFF_STATUS = Set.of("DP");
    // S-08: confirm qualification mapping.
    static final Map<String, String> QUALIFICATION = Map.of("NQ", "Non-Qualified", "IRA", "IRA", "ROTH", "Roth IRA");
    static final String PLAN_CODE = "PLAN_CODE";
    static final String RESPONSE_TIME_UTC = "response-time-utc";

    private final SummaryProperties provisional;
    private final Clock clock;

    @Autowired
    public SummaryMapper(SummaryProperties provisional) {
        this(provisional, Clock.systemUTC());
    }

    SummaryMapper(SummaryProperties provisional, Clock clock) {
        require(provisional.getCarrierId() != null && !provisional.getCarrierId().isBlank(), "carrier-id");
        require(provisional.getIssueType() != null && !provisional.getIssueType().isBlank(), "issue-type");
        require(RESPONSE_TIME_UTC.equals(provisional.getRefreshTimeSource()), "refresh-time-source");
        require(PLAN_CODE.equals(provisional.getPlanCodeSource()), "plan-code-source");
        require(!provisional.getProductTypes().isEmpty(), "product-types");
        this.provisional = provisional;
        this.clock = clock;
    }

    public PolicySummary map(Map<String, Object> row) {
        String status = text(row, "STATUS_CODE");
        if (status != null && SIGNOFF_STATUS.contains(status)) {
            throw new UnmappedValue("policy.status.unmapped", "Policy status has no IRI value pending business sign-off");
        }
        // S-summary-1: codes outside the lineage maps are rejected rather than guessed.
        String policyStatus = lookup(POLICY_STATUS, status, "policy.status.unmapped", "Policy status");
        String qualificationType = lookup(QUALIFICATION, text(row, "QUALIFICATION_CODE"),
                "policy.qualification.unmapped", "Qualification type");
        String planCode = text(row, provisional.getPlanCodeSource()); // S-07: PLAN_CODE, not PRODUCT_CODE
        String productType = lookup(provisional.getProductTypes(), planCode,
                "policy.product.unmapped", "Product type"); // S-06
        return new PolicySummary(
                date(row.get("EFFECTIVE_DATE")).toString(),
                provisional.getCarrierId(), // S-03
                Instant.now(clock).truncatedTo(ChronoUnit.SECONDS).toString(), // S-05: response time, UTC
                new PolicySummary.Product(text(row, "PRODUCT_NAME"), productType, planCode),
                qualificationType,
                policyStatus,
                provisional.getIssueType(), // S-04
                text(row, "ISSUE_STATE"),
                text(row, "CURRENCY_CODE"));
    }

    static LocalDate date(Object value) {
        if (value instanceof Timestamp timestamp) {
            return timestamp.toLocalDateTime().toLocalDate();
        }
        if (value instanceof java.sql.Date date) {
            return date.toLocalDate();
        }
        if (value instanceof LocalDateTime dateTime) {
            return dateTime.toLocalDate();
        }
        if (value instanceof LocalDate date) {
            return date;
        }
        throw new IllegalStateException("Unsupported date value");
    }

    private static String lookup(Map<String, String> map, String code, String errorCode, String element) {
        String value = code == null ? null : map.get(code);
        if (value == null) {
            throw new UnmappedValue(errorCode, element + " code has no IRI mapping");
        }
        return value;
    }

    private static String text(Map<String, Object> row, String column) {
        Object value = row.get(column);
        return value == null ? null : value.toString();
    }

    private static void require(boolean condition, String property) {
        if (!condition) {
            throw new IllegalStateException("Unsupported iri.provisional.summary." + property);
        }
    }
}
