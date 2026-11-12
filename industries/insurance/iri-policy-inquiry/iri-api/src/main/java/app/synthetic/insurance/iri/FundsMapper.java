package app.synthetic.insurance.iri;

import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class FundsMapper {
    static final String VALUATION_DATE_SOURCE = "policy_values.valuation_date";
    private static final Set<String> ACCOUNT_TYPES = Set.of("FIXED", "INDEXED", "VARIABLE", "SWEEP", "LOAN", "OTHER");
    private static final BigDecimal MAX_AMOUNT = new BigDecimal("9999999999.99");
    private static final int UNIT_VALUE_SCALE = 6;
    private static final int FUND_VALUE_SCALE = 2;

    private final String accountType;

    public FundsMapper(@Value("${iri.provisional.funds.account-type}") String accountType, // S-13
                       @Value("${iri.provisional.funds.valuation-date-source}") String valuationDateSource) { // S-14
        if (!ACCOUNT_TYPES.contains(accountType)) {
            throw new IllegalStateException("iri.provisional.funds.account-type is not an IRI fundAccountType: " + accountType);
        }
        if (!VALUATION_DATE_SOURCE.equals(valuationDateSource)) {
            throw new IllegalStateException("Unsupported iri.provisional.funds.valuation-date-source: " + valuationDateSource);
        }
        this.accountType = accountType;
    }

    public PolicyFunds map(List<FundsRepository.FundRow> rows, int startIndex, int limit) {
        List<Fund> funds = rows.stream().skip(startIndex).limit(limit).map(this::fund).toList();
        return new PolicyFunds(startIndex, funds.size(), rows.size(), funds);
    }

    Fund fund(FundsRepository.FundRow row) {
        if (row.valuationDate() == null) {
            // S-funds-1: no policy_values row, so the required fundValuationDate (S-14) has no source.
            throw new UnmappedValue("policy.funds.valuationDateMissing",
                    "Fund valuation date is unavailable for this policy");
        }
        return new Fund(accountType, row.fundCode(), row.fundName(),
                amount(row.unitValue(), UNIT_VALUE_SCALE), row.valuationDate(),
                amount(row.fundValue(), FUND_VALUE_SCALE));
    }

    static BigDecimal impliedDecimal(BigDecimal value, int scale) {
        return new BigDecimal(value.movePointRight(scale).toBigIntegerExact()).movePointLeft(scale);
    }

    private static BigDecimal amount(BigDecimal value, int scale) {
        BigDecimal result = impliedDecimal(value, scale);
        if (result.signum() < 0 || result.compareTo(MAX_AMOUNT) > 0) {
            // S-funds-2: legacy digits allow values the IRI number range rejects.
            throw new UnmappedValue("policy.funds.valueOutOfRange", "Fund amount is outside the IRI range");
        }
        return result;
    }

    @JsonPropertyOrder({"startIndex", "itemsCount", "totalItemsCount", "funds"})
    public record PolicyFunds(int startIndex, int itemsCount, int totalItemsCount, List<Fund> funds) {}

    @JsonPropertyOrder({"fundAccountType", "fundId", "fundName", "fundPrice", "fundValuationDate", "totalFundValue"})
    public record Fund(String fundAccountType, String fundId, String fundName, BigDecimal fundPrice,
                       LocalDate fundValuationDate, BigDecimal totalFundValue) {}
}
