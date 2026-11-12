package app.synthetic.insurance.iri;

import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class InfrastructureTest {
    private JdbcTemplate jdbc;
    private MockMvc mvc;

    @BeforeEach
    void setup() {
        jdbc = mock(JdbcTemplate.class);
        ObjectMapper mapper = new ObjectMapper().registerModule(new JavaTimeModule());
        mapper.disable(com.fasterxml.jackson.databind.SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        mvc = MockMvcBuilders.standaloneSetup(new HealthController(jdbc), new Failures())
                .setControllerAdvice(new InquiryAdvice())
                .setMessageConverters(new MappingJackson2HttpMessageConverter(mapper))
                .addFilters(new CorrelationFilter()).build();
    }

    @Test
    void parsesPolicyNumbers() {
        assertEquals(1200137L, PolicyNumbers.parse("0001200137"));
        assertEquals("1200137", PolicyNumbers.canonical("0001200137"));
        assertEquals(1L, PolicyNumbers.parse("000000000000000000000000000001"));
        assertEquals(0L, PolicyNumbers.parse("0"));
        assertEquals(Long.MAX_VALUE, PolicyNumbers.parse(Long.toString(Long.MAX_VALUE)));
        for (String value : new String[] {"", "ABC123", "-1", " 1", "１２３", "1".repeat(31), "9223372036854775808"}) {
            assertThrows(IllegalArgumentException.class, () -> PolicyNumbers.parse(value));
        }
        assertThrows(IllegalArgumentException.class, () -> PolicyNumbers.parse(null));
    }

    @Test
    void healthAndCorrelation() throws Exception {
        when(jdbc.queryForObject("SELECT 1 FROM dual", Integer.class)).thenReturn(1);
        mvc.perform(get("/health").header("correlationId", "caller-id"))
                .andExpect(status().isOk()).andExpect(header().string("correlationId", "caller-id"))
                .andExpect(jsonPath("$.STATUS").value("UP")).andExpect(jsonPath("$.DB").value("UP"));
        String generated = mvc.perform(get("/health")).andReturn().getResponse().getHeader("correlationId");
        assertDoesNotThrow(() -> UUID.fromString(generated));
        when(jdbc.queryForObject("SELECT 1 FROM dual", Integer.class))
                .thenThrow(new DataAccessResourceFailureException("offline"));
        mvc.perform(get("/health")).andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.DB").value("DOWN"));
    }

    @Test
    void errorsMatchSchema() throws Exception {
        String[] paths = {"invalid", "missing", "unavailable", "unmapped", "custom"};
        int[] statuses = {400, 404, 503, 422, 422};
        String[] codes = {"policy.inquiry.invalidPolicyNumber", "policy.inquiry.notFound",
                "policy.inquiry.unavailable", "policy.status.unmapped", "policy.value.unmapped"};
        for (int i = 0; i < paths.length; i++) {
            var response = mvc.perform(get("/test/" + paths[i]).header("correlationId", "error-id"))
                    .andExpect(status().is(statuses[i])).andExpect(jsonPath("$.code").value(codes[i]))
                    .andExpect(header().string("correlationId", "error-id"))
                    .andReturn().getResponse();
            SchemaAssertions.assertValid("Error", response.getContentAsString());
        }
    }

    @RestController
    static class Failures {
        @GetMapping("/test/invalid") public void invalid() { throw new IllegalArgumentException("Invalid policy"); }
        @GetMapping("/test/missing") public void missing() { throw new NotFound("Missing policy"); }
        @GetMapping("/test/unavailable") public void unavailable() { throw new DataAccessResourceFailureException("secret DB detail"); }
        @GetMapping("/test/unmapped") public void unmapped() { throw new UnmappedValue("Unmapped status"); }
        @GetMapping("/test/custom") public void custom() { throw new UnmappedValue("policy.value.unmapped", "Unmapped value"); }
    }
}
