package app.synthetic.insurance.iri.summary;

import app.synthetic.insurance.iri.shared.ApiException;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SummaryController {
    private final JdbcTemplate jdbc;
    private final String carrierId;
    private final String carrierName;

    public SummaryController(JdbcTemplate jdbc, @Value("${IRI_CARRIER_ID:}") String carrierId,
                             @Value("${IRI_CARRIER_NAME:}") String carrierName) {
        this.jdbc = jdbc;
        this.carrierId = carrierId.isEmpty() ? null : carrierId;
        this.carrierName = carrierName.isEmpty() ? null : carrierName;
    }

    @GetMapping("/v1/policies/{policyNumber}/summary")
    public PolicySummary getPolicySummary(@PathVariable String policyNumber) {
        long number;
        try {
            if (!policyNumber.matches("[0-9]+")) {
                throw new NumberFormatException();
            }
            number = Long.parseLong(policyNumber);
        } catch (NumberFormatException error) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "Invalid policy number");
        }
        Map<String, Object> row = jdbc.queryForList(
                "SELECT * FROM annuity_policy WHERE contract_no = ?", number).stream().findFirst()
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Policy not found"));
        String status = text(row, "STATUS_CODE");
        status = switch (status) {
            case "IF" -> "ACTIVE";
            case "LP" -> "LAPSED";
            case "SR" -> "SURRENDERED";
            case "TM" -> "TERMINATED";
            case "PI" -> "PENDINGISSUED";
            default -> status;
        };
        String qualification = text(row, "QUALIFICATION_CODE");
        qualification = switch (qualification) {
            case "NQ" -> "Non-Qualified";
            case "IRA" -> "IRA";
            case "ROTH" -> "Roth IRA";
            default -> qualification;
        };
        Object effective = row.get("EFFECTIVE_DATE");
        LocalDate date = effective instanceof Timestamp timestamp ? timestamp.toLocalDateTime().toLocalDate()
                : effective instanceof java.sql.Date sqlDate ? sqlDate.toLocalDate() : (LocalDate) effective;
        return new PolicySummary(status, new PolicySummary.Product(text(row, "PRODUCT_NAME"),
                text(row, "PLAN_CODE"), text(row, "PRODUCT_CODE"), null), qualification,
                date.toString(), text(row, "ISSUE_STATE"), text(row, "CURRENCY_CODE"),
                carrierId, carrierName, null, null, Map.of("GRX_IND", text(row, "GRX_IND")));
    }

    private static String text(Map<String, Object> row, String column) {
        return row.get(column).toString();
    }
}
