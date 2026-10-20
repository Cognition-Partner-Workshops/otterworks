package com.otterworks.commission.splits;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;

class SplitsControllerTest {

    private static final String POLICY_ID = "731904";

    private SplitsService service;
    private SplitsController controller;
    private Logger logger;
    private ListAppender<ILoggingEvent> appender;

    @BeforeEach
    void setUp() {
        service = mock(SplitsService.class);
        controller = new SplitsController(service);
        logger = (Logger) LoggerFactory.getLogger(SplitsController.class);
        appender = new ListAppender<>();
        appender.start();
        logger.addAppender(appender);
    }

    @AfterEach
    void tearDown() {
        logger.detachAppender(appender);
    }

    @Test
    @DisplayName("request log line carries no policy identifier (carrier.log-policy-claim-identifier)")
    void requestLogOmitsPolicyId() {
        List<SplitAllocation> splits = List.of(
                new SplitAllocation(11L, new BigDecimal("60")),
                new SplitAllocation(12L, new BigDecimal("40")));
        when(service.setSplits(eq(731904L), any(), anyString())).thenReturn(2);

        Map<String, Object> body = controller.setSplits(POLICY_ID, new SetSplitsRequest(splits, "OPS_USER"));

        assertThat(body).containsEntry("policy_id", 731904L).containsEntry("agents", 2);
        assertThat(appender.list).hasSize(1);
        String line = appender.list.get(0).getFormattedMessage();
        assertThat(line).isEqualTo("POST /policies/{policyId}/splits agents=2 actor=OPS_USER");
        assertThat(line).doesNotContain(POLICY_ID);
        assertThat(appender.list.get(0).getArgumentArray()).doesNotContain(POLICY_ID, 731904L);
    }

    @Test
    @DisplayName("NULL policy id and NULL collection still log without an identifier")
    void requestLogWithNulls() {
        when(service.setSplits(eq(null), eq(null), anyString())).thenReturn(0);

        controller.setSplits("null", new SetSplitsRequest(null, "OPS_USER"));

        assertThat(appender.list.get(0).getFormattedMessage())
                .isEqualTo("POST /policies/{policyId}/splits agents=null actor=OPS_USER");
    }
}
