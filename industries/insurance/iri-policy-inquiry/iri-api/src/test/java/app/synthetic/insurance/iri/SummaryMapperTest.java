package app.synthetic.insurance.iri;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.nio.file.Path;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.ConfigurationPropertySources;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.io.ClassPathResource;
import static org.junit.jupiter.api.Assertions.*;

class SummaryMapperTest {
    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-06-30T12:34:56.789Z"), ZoneOffset.UTC);
    private final ObjectMapper json = new ObjectMapper().registerModule(new JavaTimeModule())
            .disable(com.fasterxml.jackson.databind.SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    private SummaryMapper mapper;

    static SummaryProperties configured() throws Exception {
        var sources = new YamlPropertySourceLoader().load("application", new ClassPathResource("application.yml"));
        return new Binder(ConfigurationPropertySources.from(sources))
                .bind("iri.provisional.summary", SummaryProperties.class).get();
    }

    static Map<String, Object> row(JsonNode legacy) {
        Map<String, Object> row = new LinkedHashMap<>();
        String[][] columns = {{"STATUS_CODE", "STAT_CD"}, {"PRODUCT_CODE", "PROD_CD"}, {"PRODUCT_NAME", "PROD_NM"},
                {"PLAN_CODE", "PLAN_CD"}, {"QUALIFICATION_CODE", "QUAL_CD"}, {"ISSUE_STATE", "ISS_ST"},
                {"CURRENCY_CODE", "CCY_CD"}, {"GRX_IND", "GRX_IND"}};
        for (String[] column : columns) {
            row.put(column[0], legacy.get(column[1]).asText());
        }
        row.put("EFFECTIVE_DATE", Timestamp.valueOf(LocalDate.parse(legacy.get("EFF_DT").asText(),
                DateTimeFormatter.BASIC_ISO_DATE).atStartOfDay()));
        return row;
    }

    @BeforeEach
    void setup() throws Exception {
        mapper = new SummaryMapper(configured(), CLOCK);
    }

    @Test
    void provisionalConfigMatchesLineage() throws Exception {
        SummaryProperties properties = configured();
        assertEquals("SYNANN", properties.getCarrierId());
        assertEquals("GUARANTEED", properties.getIssueType());
        assertEquals("response-time-utc", properties.getRefreshTimeSource());
        assertEquals("PLAN_CODE", properties.getPlanCodeSource());
        assertEquals(Map.of("FIXED", "FIXED", "FLEX", "DEFERRED"), properties.getProductTypes());
    }

    @Test
    void everyFrozenSuccessCaseMapsToValidSummary() throws Exception {
        JsonNode cases = json.readTree(Path.of("../parity/frozen/summary.json").toFile());
        int mapped = 0;
        int signoff = 0;
        for (JsonNode c : cases) {
            if (c.get("status").asInt() != 200) {
                continue;
            }
            JsonNode legacy = c.get("body");
            if ("DP".equals(legacy.get("STAT_CD").asText())) {
                UnmappedValue error = assertThrows(UnmappedValue.class, () -> mapper.map(row(legacy)));
                assertEquals("policy.status.unmapped", error.code());
                SchemaAssertions.assertValid("Error", json.writeValueAsString(
                        new ErrorBody(error.code(), error.getMessage(), Instant.now())));
                signoff++;
                continue;
            }
            String body = json.writeValueAsString(mapper.map(row(legacy)));
            SchemaAssertions.assertValid("PolicySummary", body);
            JsonNode iri = json.readTree(body);
            String id = c.get("case_id").asText();
            assertEquals(SummaryMapper.POLICY_STATUS.get(legacy.get("STAT_CD").asText()), iri.get("policyStatus").asText(), id);
            assertEquals(legacy.get("PROD_NM").asText(), iri.at("/product/planName").asText(), id);
            assertEquals(legacy.get("PLAN_CD").asText(), iri.at("/product/planCode").asText(), id);
            assertEquals(Map.of("FIXED", "FIXED", "FLEX", "DEFERRED").get(legacy.get("PLAN_CD").asText()),
                    iri.at("/product/productType").asText(), id);
            assertEquals(Map.of("NQ", "Non-Qualified", "IRA", "IRA", "ROTH", "Roth IRA").get(legacy.get("QUAL_CD").asText()),
                    iri.get("qualificationType").asText(), id);
            assertEquals(legacy.get("ISS_ST").asText(), iri.get("issueState").asText(), id);
            assertEquals(legacy.get("CCY_CD").asText(), iri.get("currency").asText(), id);
            assertEquals(LocalDate.parse(legacy.get("EFF_DT").asText(), DateTimeFormatter.BASIC_ISO_DATE).toString(),
                    iri.get("effectiveDate").asText(), id);
            assertEquals("SYNANN", iri.get("carrierId").asText(), id);
            assertEquals("GUARANTEED", iri.get("issueType").asText(), id);
            assertEquals("2026-06-30T12:34:56Z", iri.get("policyLastRefreshDateTime").asText(), id);
            assertFalse(iri.has("policyNumber"), id);
            assertFalse(body.contains(legacy.get("CNTR_NO").asText()), id);
            assertFalse(body.contains(legacy.get("PROD_CD").asText()), id);
            assertFalse(iri.has("GRX_IND") || iri.has("grxInd"), id);
            mapped++;
        }
        assertEquals(101, mapped + signoff);
        assertTrue(signoff > 0);
    }

    @Test
    void acceptsOracleDateRepresentations() {
        LocalDate expected = LocalDate.of(2015, 1, 25);
        assertEquals(expected, SummaryMapper.date(Timestamp.valueOf(expected.atTime(23, 59))));
        assertEquals(expected, SummaryMapper.date(java.sql.Date.valueOf(expected)));
        assertEquals(expected, SummaryMapper.date(expected.atStartOfDay()));
        assertEquals(expected, SummaryMapper.date(expected));
        assertThrows(IllegalStateException.class, () -> SummaryMapper.date("20150125"));
    }

    @Test
    void codesOutsideLineageMapsAreRejected() throws Exception {
        Map<String, Object> base = Map.of("STATUS_CODE", "IF", "PRODUCT_NAME", "Steady Income Annuity",
                "PLAN_CODE", "FIXED", "QUALIFICATION_CODE", "NQ", "ISSUE_STATE", "AZ", "CURRENCY_CODE", "USD",
                "EFFECTIVE_DATE", LocalDate.of(2015, 1, 25));
        SchemaAssertions.assertValid("PolicySummary", json.writeValueAsString(mapper.map(base)));
        String[][] cases = {{"STATUS_CODE", "XX", "policy.status.unmapped"},
                {"QUALIFICATION_CODE", "SEP", "policy.qualification.unmapped"},
                {"PLAN_CODE", "VAR", "policy.product.unmapped"}};
        for (String[] c : cases) {
            Map<String, Object> row = new LinkedHashMap<>(base);
            row.put(c[0], c[1]);
            UnmappedValue error = assertThrows(UnmappedValue.class, () -> mapper.map(row));
            assertEquals(c[2], error.code());
            SchemaAssertions.assertValid("Error", json.writeValueAsString(
                    new ErrorBody(error.code(), error.getMessage(), Instant.now())));
            Map<String, Object> missing = new LinkedHashMap<>(base);
            missing.remove(c[0]);
            assertEquals(c[2], assertThrows(UnmappedValue.class, () -> mapper.map(missing)).code());
        }
    }

    @Test
    void rejectsUnsupportedProvisionalSources() throws Exception {
        SummaryProperties productCode = configured();
        productCode.setPlanCodeSource("PRODUCT_CODE");
        assertThrows(IllegalStateException.class, () -> new SummaryMapper(productCode, CLOCK));
        SummaryProperties refresh = configured();
        refresh.setRefreshTimeSource("legacy");
        assertThrows(IllegalStateException.class, () -> new SummaryMapper(refresh, CLOCK));
        SummaryProperties carrier = configured();
        carrier.setCarrierId(" ");
        assertThrows(IllegalStateException.class, () -> new SummaryMapper(carrier, CLOCK));
    }
}
