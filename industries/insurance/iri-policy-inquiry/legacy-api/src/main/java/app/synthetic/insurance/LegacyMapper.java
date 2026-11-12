package app.synthetic.insurance;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class LegacyMapper {
    private LegacyMapper() {}

    public static String digits(Object value, int width, int scale) {
        String result = new BigDecimal(value.toString()).movePointRight(scale).toBigIntegerExact().toString();
        if (result.startsWith("-") || result.length() > width) {
            throw new IllegalArgumentException("Numeric field out of range");
        }
        return "0".repeat(width - result.length()) + result;
    }

    public static String date(Object value) {
        LocalDate date = value instanceof Timestamp ? ((Timestamp) value).toLocalDateTime().toLocalDate()
                : value instanceof java.sql.Date ? ((java.sql.Date) value).toLocalDate() : (LocalDate) value;
        return date.format(DateTimeFormatter.BASIC_ISO_DATE);
    }

    public static Map<String, String> success() {
        Map<String, String> result = new LinkedHashMap<>();
        result.put("RTN_CD", "00");
        return result;
    }

    public static Map<String, String> summary(Map<String, Object> row) {
        Map<String, String> result = success();
        String[][] fields = {{"CNTR_NO", "CONTRACT_NO"}, {"STAT_CD", "STATUS_CODE"},
                {"PROD_CD", "PRODUCT_CODE"}, {"PROD_NM", "PRODUCT_NAME"}, {"PLAN_CD", "PLAN_CODE"},
                {"QUAL_CD", "QUALIFICATION_CODE"}, {"ISS_ST", "ISSUE_STATE"}, {"OWN_NM", "OWNER_NAME"},
                {"ANN_NM", "ANNUITANT_NAME"}, {"CCY_CD", "CURRENCY_CODE"}, {"GRX_IND", "GRX_IND"}};
        for (String[] field : fields) {
            result.put(field[0], row.get(field[1]).toString());
        }
        result.put("ISS_DT", date(row.get("ISSUE_DATE")));
        result.put("EFF_DT", date(row.get("EFFECTIVE_DATE")));
        result.put("MAT_DT", date(row.get("MATURITY_DATE")));
        return result;
    }

    public static Map<String, String> values(Map<String, Object> row) {
        Map<String, String> result = success();
        result.put("CNTR_NO", digits(row.get("CONTRACT_NO"), 10, 0));
        result.put("VAL_DT", date(row.get("VALUATION_DATE")));
        String[][] fields = {{"ACCT_VAL", "ACCOUNT_VALUE"}, {"SURR_VAL", "SURRENDER_VALUE"},
                {"CASH_VAL", "CASH_VALUE"}, {"PREM_TD", "PREMIUMS_TO_DATE"},
                {"WDR_TD", "WITHDRAWALS_TO_DATE"}, {"DTH_BEN", "DEATH_BENEFIT"}, {"SURR_CHG", "SURRENDER_CHARGE"}};
        for (String[] field : fields) {
            result.put(field[0], digits(row.get(field[1]), 15, 2));
        }
        return result;
    }

    public static Map<String, String> funds(long contract, List<Map<String, Object>> rows) {
        Map<String, String> result = success();
        result.put("CNTR_NO", Long.toString(contract));
        result.put("FUND_CNT", Integer.toString(rows.size()));
        for (int i = 0; i < rows.size(); i++) {
            Map<String, Object> row = rows.get(i);
            String suffix = String.format(Locale.ROOT, "_%02d", i + 1);
            result.put("FUND_CD" + suffix, row.get("FUND_CODE").toString());
            result.put("FUND_NM" + suffix, row.get("FUND_NAME").toString());
            result.put("ALLOC_PCT" + suffix, digits(row.get("ALLOCATION_PCT"), 5, 2));
            result.put("FUND_UNITS" + suffix, digits(row.get("FUND_UNITS"), 18, 6));
            result.put("UNIT_VAL" + suffix, digits(row.get("UNIT_VALUE"), 15, 6));
            result.put("FUND_VAL" + suffix, digits(row.get("FUND_VALUE"), 15, 2));
        }
        return result;
    }
}
