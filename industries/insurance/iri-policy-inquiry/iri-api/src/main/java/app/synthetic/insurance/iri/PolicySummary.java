package app.synthetic.insurance.iri;

import com.fasterxml.jackson.annotation.JsonInclude;

/** IRI v1.1.5 PolicySummary; policyNumber is never echoed (changelog C-2). */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record PolicySummary(String effectiveDate, String carrierId, String policyLastRefreshDateTime,
                            Product product, String qualificationType, String policyStatus,
                            String issueType, String issueState, String currency) {

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Product(String planName, String productType, String planCode) {}
}
