package app.synthetic.insurance.iri;

import app.synthetic.insurance.iri.shared.ApiException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Bean;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.mockito.Mockito.when;

@SpringBootTest(properties = "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration")
@AutoConfigureMockMvc
class SharedApiTest {
    @Autowired MockMvc mvc;
    @MockBean JdbcTemplate jdbc;

    @Test void healthAndEcho() throws Exception {
        when(jdbc.queryForObject("SELECT 1 FROM dual", Integer.class)).thenReturn(1);
        mvc.perform(get("/health").header("correlationId", "test-correlation"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.STATUS").value("UP"))
            .andExpect(jsonPath("$.DB").value("UP"))
            .andExpect(header().string("correlationId", "test-correlation"));
    }

    @Test void healthWhenDatabaseUnavailable() throws Exception {
        when(jdbc.queryForObject("SELECT 1 FROM dual", Integer.class))
            .thenThrow(new DataAccessResourceFailureException("unreachable"));
        mvc.perform(get("/health")).andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.STATUS").value("DOWN"))
            .andExpect(jsonPath("$.DB").value("DOWN"));
    }

    @Test void healthWhenDatabaseReturnsUnexpectedResult() throws Exception {
        when(jdbc.queryForObject("SELECT 1 FROM dual", Integer.class)).thenReturn(null);
        mvc.perform(get("/health")).andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.STATUS").value("DOWN"))
            .andExpect(jsonPath("$.DB").value("DOWN"));
    }

    @Test void missingResource() throws Exception {
        mvc.perform(get("/absent")).andExpect(status().isNotFound())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.NotFound"))
            .andExpect(jsonPath("$.message").isString())
            .andExpect(jsonPath("$.correlationId").doesNotExist())
            .andExpect(header().exists("correlationId"));
    }

    @Test void errors() throws Exception {
        mvc.perform(get("/test/invalid")).andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.Invalid"));
        mvc.perform(get("/test/missing")).andExpect(status().isNotFound())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.NotFound"));
        mvc.perform(get("/test/unavailable")).andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.Unavailable"))
            .andExpect(jsonPath("$.message").value("Policy inquiry data unavailable"));
    }

    @TestConfiguration
    static class Config {
        @Bean FaultController faults() { return new FaultController(); }
    }

    @RestController
    static class FaultController {
        @GetMapping("/test/invalid") void invalid() { throw new IllegalArgumentException(); }
        @GetMapping("/test/missing") void missing() { throw new ApiException(HttpStatus.NOT_FOUND, "No policy"); }
        @GetMapping("/test/unavailable") void unavailable() {
            throw new DataAccessResourceFailureException("must not leak credentials");
        }
    }
}
