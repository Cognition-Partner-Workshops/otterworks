package com.otterworks.commission.common;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import com.otterworks.commission.calculation.CalculationController;
import com.otterworks.commission.calculation.CalculationService;
import com.otterworks.commission.splits.SplitsController;
import com.otterworks.commission.splits.SplitsService;

/** The attack path from the finding: a forged {@code ledger-run} actor without the delegate's token. */
@WebMvcTest(controllers = {SplitsController.class, CalculationController.class},
        properties = "commission.caller-token=test-token")
class CallerAuthWiringTest {

    private static final String SPLITS = "{\"splits\":[{\"agent_id\":1,\"split_pct\":\"100\"}],\"actor\":\"ledger-run\"}";
    private static final String CALC = "{\"period_month\":\"2026-03\",\"actor\":\"ledger-run\"}";

    @Autowired
    private MockMvc mvc;

    @MockBean
    private SplitsService splits;

    @MockBean
    private CalculationService calculation;

    @Test
    @DisplayName("unauthenticated splits and commission calls are refused before any rule or audit row runs")
    void refusesUnauthenticated() throws Exception {
        mvc.perform(post("/policies/4/splits").contentType(MediaType.APPLICATION_JSON).content(SPLITS))
                .andExpect(status().isUnauthorized());
        mvc.perform(post("/policies/4/commission").contentType(MediaType.APPLICATION_JSON).content(CALC))
                .andExpect(status().isUnauthorized());
        mvc.perform(post("/policies/4/splits").header("Authorization", "Bearer guess")
                .contentType(MediaType.APPLICATION_JSON).content(SPLITS))
                .andExpect(status().isUnauthorized());
        verifyNoInteractions(splits, calculation);
    }

    @Test
    @DisplayName("the delegate's token reaches the rule with the package caller's actor")
    void acceptsDelegate() throws Exception {
        when(splits.setSplits(eq(4L), any(), eq("ledger-run"))).thenReturn(1);
        mvc.perform(post("/policies/4/splits").header("Authorization", "Bearer test-token")
                .contentType(MediaType.APPLICATION_JSON).content(SPLITS))
                .andExpect(status().isOk());
        verify(splits).setSplits(eq(4L), any(), eq("ledger-run"));
    }
}
