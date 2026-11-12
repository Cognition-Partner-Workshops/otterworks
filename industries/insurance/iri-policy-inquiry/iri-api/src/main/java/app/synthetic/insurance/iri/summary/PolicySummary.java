package app.synthetic.insurance.iri.summary;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.Map;

@JsonInclude(JsonInclude.Include.ALWAYS)
public record PolicySummary(String policyStatus, Product product, String qualificationType,
        String effectiveDate, String issueState, String currency, String carrierId,
        String carrierName, String issueType, String policyLastRefreshDateTime,
        Map<String, String> legacyUnmapped) {
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record Product(String planName, String planCode, String shortName, String productType) {}
}
