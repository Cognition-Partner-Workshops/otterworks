package com.otterworks.commission.screens;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import com.otterworks.commission.common.Backend;
import com.otterworks.commission.screens.ScreensRepository.Agent;
import com.otterworks.commission.screens.ScreensRepository.Database;
import com.otterworks.commission.screens.ScreensRepository.RateRow;
import com.otterworks.commission.screens.ScreensRepository.StatementRow;

@WebMvcTest(ScreensController.class)
class ScreensControllerTest {

    private static final LocalDateTime AT = LocalDateTime.of(2026, 10, 20, 7, 0);

    @Autowired
    private MockMvc mvc;

    @MockBean
    private ScreensRepository repo;

    @MockBean
    private Backend backend;

    @BeforeEach
    void setUp() {
        when(backend.kind()).thenReturn(Backend.Kind.POSTGRES);
        when(repo.database()).thenReturn(new Database("PostgreSQL 16.4", "jdbc:postgresql://localhost/commission"));
        when(repo.findAgent(1)).thenReturn(Optional.of(new Agent(1, "AG-100", "Ada Agent", "ACTIVE")));
        when(repo.statement(1, "2026-03")).thenReturn(List.of(
                new StatementRow(10, 1, "POL-1", "AUTO-STD", new BigDecimal("1800.00"), 4, new BigDecimal("9.50"),
                        new BigDecimal("100.00"), new BigDecimal("14.25"), AT, "commission-service"),
                new StatementRow(11, 2, "POL-2", "HOME-STD", new BigDecimal("12345.60"), 2, new BigDecimal("8.00"),
                        new BigDecimal("60.00"), new BigDecimal("1049.38"), AT, "commission-service")));
        when(repo.rateHistory(1)).thenReturn(List.of(
                new RateRow(2, "HOME-STD", null, null, new BigDecimal("8.00"), LocalDate.of(2025, 1, 1), null),
                new RateRow(3, "HOME-STD", 1L, "AG-100", new BigDecimal("9.00"), LocalDate.of(2025, 1, 1),
                        LocalDate.of(2025, 5, 31)),
                new RateRow(4, "AUTO-STD", null, null, new BigDecimal("9.50"), LocalDate.of(2026, 1, 1), null)));
    }

    @Test
    void statementShowsRowsAndExactTotal() throws Exception {
        mvc.perform(get("/screens/statement").param("agent", "1").param("period", "2026-03"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("backend <span>POSTGRES</span>")))
                .andExpect(content().string(containsString("12,345.60")))
                .andExpect(content().string(containsString("1,049.38")))
                .andExpect(content().string(containsString("<td class=\"num\" id=\"total\">1,063.63</td>")))
                .andExpect(content().string(containsString("commission-service")));
    }

    @Test
    void rateHistoryMarksRatesUsedByTheStatement() throws Exception {
        mvc.perform(get("/screens/rates").param("agent", "1").param("period", "2026-03"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<tr class=\"used\">")))
                .andExpect(content().string(containsString("2025-05-31")))
                .andExpect(content().string(containsString("open")));
    }

    @Test
    void emptyPeriodShowsZeroTotal() throws Exception {
        mvc.perform(get("/screens/statement").param("agent", "1").param("period", "2024-01"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("No ledger rows")))
                .andExpect(content().string(containsString("<td class=\"num\" id=\"total\">0.00</td>")));
    }

    @Test
    void malformedPeriodIs400() throws Exception {
        mvc.perform(get("/screens/statement").param("agent", "1").param("period", "2026-13"))
                .andExpect(status().isBadRequest())
                .andExpect(content().string(containsString("period must be YYYY-MM")))
                .andExpect(content().string(not(containsString("id=\"total\""))));
    }

    @Test
    void unknownAgentIs404() throws Exception {
        mvc.perform(get("/screens/statement").param("agent", "99").param("period", "2026-03"))
                .andExpect(status().isNotFound())
                .andExpect(content().string(containsString("Unknown agent: 99")));
    }
}
