package app.synthetic.insurance.iri.funds;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.math.BigDecimal;
import java.util.List;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record PolicyFunds(int startIndex, int itemsCount, int totalItemsCount, List<Fund> funds) {
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Fund(String fundId, String fundName, BigDecimal fundPrice, BigDecimal totalFundValue,
                       String fundValuationDate, List<Segment> fundSegments) {}

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Segment(BigDecimal numberOfUnits) {}
}
