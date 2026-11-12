package app.synthetic.insurance.iri.values;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration")
@AutoConfigureMockMvc
class PolicyValuesControllerTest {
    @Autowired MockMvc mvc;
    @MockBean JdbcTemplate jdbc;
    @MockBean PolicyValuesRepository repository;

    static PolicyValuesRow row(String withdrawals) {
        return new PolicyValuesRow(1200137L, LocalDate.of(2026, 6, 30), new BigDecimal("51250"),
                new BigDecimal("49750.00"), new BigDecimal("49750"), new BigDecimal("46100"),
                new BigDecimal(withdrawals), new BigDecimal("56250"), new BigDecimal("1500"));
    }

    @Test void mapsValues() throws Exception {
        when(repository.find(1200137L)).thenReturn(Optional.of(row("50")));
        mvc.perform(get("/v1/policies/0001200137/values").header("correlationId", "c-1"))
            .andExpect(status().isOk())
            .andExpect(header().string("correlationId", "c-1"))
            .andExpect(jsonPath("$.valuesAsOfDate").value("2026-06-30"))
            .andExpect(jsonPath("$.totalDepositITD").value(46100.00))
            .andExpect(jsonPath("$.accountValues.endingAccountValue").value(51250.00))
            .andExpect(jsonPath("$.accountValues.surrenderValue").value(49750.00))
            .andExpect(jsonPath("$.accountValues.totalNetWithdrawalSinceIssue").value(50.00))
            .andExpect(jsonPath("$.legacyUnmappedValues.cashValue").value(49750.00))
            .andExpect(jsonPath("$.legacyUnmappedValues.deathBenefit").value(56250.00))
            .andExpect(jsonPath("$.legacyUnmappedValues.surrenderCharge").value(1500.00))
            .andExpect(jsonPath("$.withdrawalValues").doesNotExist())
            .andExpect(jsonPath("$.authorization").doesNotExist())
            .andExpect(jsonPath("$.correlationId").doesNotExist());
    }

    @Test void amountsAreJsonNumbersWithTwoDecimals() throws Exception {
        when(repository.find(1200137L)).thenReturn(Optional.of(row("0.1")));
        String body = mvc.perform(get("/v1/policies/1200137/values")).andReturn().getResponse().getContentAsString();
        org.junit.jupiter.api.Assertions.assertTrue(body.contains("\"totalNetWithdrawalSinceIssue\":0.10"), body);
        org.junit.jupiter.api.Assertions.assertTrue(body.contains("\"endingAccountValue\":51250.00"), body);
    }

    @Test void notFound() throws Exception {
        when(repository.find(9999999999L)).thenReturn(Optional.empty());
        mvc.perform(get("/v1/policies/9999999999/values")).andExpect(status().isNotFound())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.NotFound"))
            .andExpect(jsonPath("$.message").isString());
    }

    @Test void invalidPolicyNumber() throws Exception {
        for (String bad : new String[] {"12A4", "-1", "1".repeat(31), "99999999999999999999"}) {
            mvc.perform(get("/v1/policies/" + bad + "/values")).andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("Inquiry.Request.Invalid"));
        }
        mvc.perform(get("/v1/policies/1/values").param("associatedFirmId", "x".repeat(66)))
            .andExpect(status().isBadRequest());
    }

    @Test void outOfRangeAmountIsBadRequestLikeLegacy() throws Exception {
        when(repository.find(1200137L)).thenReturn(Optional.of(row("-1")));
        mvc.perform(get("/v1/policies/1200137/values")).andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.Invalid"));
    }

    @Test void databaseUnavailable() throws Exception {
        when(repository.find(1200137L)).thenThrow(new DataAccessResourceFailureException("down"));
        mvc.perform(get("/v1/policies/1200137/values")).andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.Unavailable"));
    }
}
