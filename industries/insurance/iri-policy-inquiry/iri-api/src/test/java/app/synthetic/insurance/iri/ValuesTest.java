package app.synthetic.insurance.iri;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ValuesTest {
    private static final ObjectMapper JSON = new ObjectMapper();
    private ValuesRepository repository;
    private MockMvc mvc;

    @BeforeEach
    void setup() {
        repository = mock(ValuesRepository.class);
        when(repository.find(anyLong())).thenReturn(Optional.empty());
        ObjectMapper mapper = new ObjectMapper().registerModule(new JavaTimeModule());
        mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        mvc = MockMvcBuilders.standaloneSetup(new ValuesController(repository, "WITHDRAWALS_TO_DATE"))
                .setControllerAdvice(new InquiryAdvice())
                .setMessageConverters(new MappingJackson2HttpMessageConverter(mapper))
                .addFilters(new CorrelationFilter()).build();
    }

    private static Map<String, Object> row(String date, String account, String surrender, String premiums,
                                           String withdrawals) {
        Map<String, Object> row = new HashMap<>();
        row.put("VALUATION_DATE", Timestamp.valueOf(LocalDate.parse(date).atStartOfDay()));
        row.put("ACCOUNT_VALUE", new BigDecimal(account));
        row.put("SURRENDER_VALUE", new BigDecimal(surrender));
        row.put("CASH_VALUE", new BigDecimal(surrender));
        row.put("PREMIUMS_TO_DATE", new BigDecimal(premiums));
        row.put("WITHDRAWALS_TO_DATE", new BigDecimal(withdrawals));
        row.put("DEATH_BENEFIT", new BigDecimal("1.00"));
        row.put("SURRENDER_CHARGE", new BigDecimal("1.00"));
        return row;
    }

    private static BigDecimal implied(JsonNode legacy, String field) {
        return new BigDecimal(legacy.get(field).asText()).movePointLeft(2);
    }

    private MockHttpServletResponse call(String policyNumber, int status) throws Exception {
        MockHttpServletResponse response = mvc.perform(get("/v1/policies/" + policyNumber + "/values")
                        .header("correlationId", "values-id"))
                .andExpect(status().is(status)).andExpect(header().string("correlationId", "values-id"))
                .andReturn().getResponse();
        SchemaAssertions.assertValid(status == 200 ? "PolicyValue" : "Error", response.getContentAsString());
        return response;
    }

    @Test
    void frozenLegacyContractsMapToSchemaValidPolicyValues() throws Exception {
        JsonNode cases = JSON.readTree(Path.of("../parity/frozen/values.json").toFile());
        int mapped = 0;
        for (JsonNode frozen : cases) {
            if (frozen.get("status").asInt() != 200) {
                continue;
            }
            JsonNode legacy = frozen.get("body");
            String date = LocalDate.parse(legacy.get("VAL_DT").asText(), DateTimeFormatter.BASIC_ISO_DATE).toString();
            long contract = Long.parseLong(legacy.get("CNTR_NO").asText());
            when(repository.find(contract)).thenReturn(Optional.of(row(date,
                    implied(legacy, "ACCT_VAL").toPlainString(), implied(legacy, "SURR_VAL").toPlainString(),
                    implied(legacy, "PREM_TD").toPlainString(), implied(legacy, "WDR_TD").toPlainString())));
            JsonNode body = JSON.readTree(call(frozen.get("policy_number").asText(), 200).getContentAsString());
            assertFalse(body.has("policyNumber"), "C-2");
            assertEquals(date, body.get("valuesAsOfDate").asText());
            assertEquals(0, implied(legacy, "ACCT_VAL").compareTo(body.at("/accountValues/endingAccountValue").decimalValue()));
            assertEquals(0, implied(legacy, "SURR_VAL").compareTo(body.at("/accountValues/surrenderValue").decimalValue()));
            assertEquals(0, implied(legacy, "WDR_TD").compareTo(body.at("/accountValues/totalNetWithdrawalSinceIssue").decimalValue()));
            assertEquals(0, implied(legacy, "PREM_TD").compareTo(body.get("totalDepositITD").decimalValue()));
            mapped++;
        }
        assertEquals(101, mapped);
    }

    @Test
    void mapsExactDecimalsAndDropsUnmappedColumns() throws Exception {
        when(repository.find(1200137L)).thenReturn(Optional.of(row("2026-06-30", "9999999999.99", "0.01", "51250", "0")));
        String body = call("0001200137", 200).getContentAsString();
        assertEquals("{\"valuesAsOfDate\":\"2026-06-30\",\"accountValues\":{\"endingAccountValue\":9999999999.99,"
                + "\"surrenderValue\":0.01,\"totalNetWithdrawalSinceIssue\":0.00},\"totalDepositITD\":51250.00}", body);
        verify(repository).find(1200137L);
    }

    @Test
    void errorsMatchSchema() throws Exception {
        assertEquals("policy.inquiry.notFound", JSON.readTree(call("9999999999", 404).getContentAsString()).get("code").asText());
        for (String invalid : new String[] {"ABC123", "1".repeat(31), "9223372036854775808"}) {
            assertEquals("policy.inquiry.invalidPolicyNumber",
                    JSON.readTree(call(invalid, 400).getContentAsString()).get("code").asText());
        }
        when(repository.find(42L)).thenThrow(new DataAccessResourceFailureException("ORA-12541 detail"));
        String unavailable = call("42", 503).getContentAsString();
        assertEquals("policy.inquiry.unavailable", JSON.readTree(unavailable).get("code").asText());
        assertFalse(unavailable.contains("ORA-"));
    }

    @Test
    void amountsOutsideIriRangeAreUnprocessable() throws Exception {
        when(repository.find(7L)).thenReturn(Optional.of(row("2026-06-30", "-0.01", "0", "0", "0")));
        when(repository.find(8L)).thenReturn(Optional.of(row("2026-06-30", "10000000000.00", "0", "0", "0")));
        for (String contract : new String[] {"7", "8"}) {
            assertEquals("policy.value.unmapped", JSON.readTree(call(contract, 422).getContentAsString()).get("code").asText());
        }
    }

    @Test
    void withdrawalSourceComesFromProvisionalConfig() {
        assertThrows(IllegalStateException.class, () -> new ValuesMapper("CASH_VALUE"));
        assertThrows(IllegalStateException.class, () -> new ValuesMapper(null));
        assertThrows(ArithmeticException.class, () -> ValuesMapper.amount(Map.of("X", new BigDecimal("1.001")), "X"));
        assertEquals(LocalDate.of(2026, 6, 30), ValuesMapper.date(java.sql.Date.valueOf("2026-06-30")));
    }
}
