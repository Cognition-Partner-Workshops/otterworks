package app.synthetic.insurance.iri.values;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonInclude;
import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * IRI PolicyValue (PolicyInquiry v1.1.5). Only elements with a legacy source are emitted;
 * withdrawalValues and authorization are omitted-optional per lineage.
 * legacyUnmappedValues carries CASH_VAL/DTH_BEN/SURR_CHG, which have no PolicyValue element,
 * pending business sign-off on their representation.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record PolicyValue(
        @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd") LocalDate valuesAsOfDate,
        BigDecimal totalDepositITD,
        AccountValues accountValues,
        LegacyUnmappedValues legacyUnmappedValues) {

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record AccountValues(BigDecimal endingAccountValue, BigDecimal surrenderValue,
                                BigDecimal totalNetWithdrawalSinceIssue) {}

    public record LegacyUnmappedValues(BigDecimal cashValue, BigDecimal deathBenefit, BigDecimal surrenderCharge) {}
}
