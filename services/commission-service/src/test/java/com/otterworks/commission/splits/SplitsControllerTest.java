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
import org.springframework.http.ResponseEntity;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;

class SplitsControllerTest {

    private static final String POLICY_ID = "731904";
    private static final String ACTOR = "OPS_USER";
    private static final String UUID_RE = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

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
    @DisplayName("request log line carries a correlation id, no policy id and no actor (carrier.log-policy-claim-identifier)")
    void requestLogOmitsPolicyIdAndActor() {
        List<SplitAllocation> splits = List.of(
                new SplitAllocation(11L, new BigDecimal("60")),
                new SplitAllocation(12L, new BigDecimal("40")));
        when(service.setSplits(eq(731904L), any(), eq(ACTOR))).thenReturn(2);

        ResponseEntity<Map<String, Object>> resp =
                controller.setSplits(POLICY_ID, new SetSplitsRequest(splits, ACTOR));

        assertThat(resp.getBody()).containsEntry("policy_id", 731904L).containsEntry("agents", 2);
        String correlationId = resp.getHeaders().getFirst(SplitsController.CORRELATION_HEADER);
        assertThat(correlationId).matches(UUID_RE);

        assertThat(appender.list).hasSize(1);
        String line = appender.list.get(0).getFormattedMessage();
        assertThat(line).isEqualTo("POST /policies/{policyId}/splits correlation_id=" + correlationId + " agents=2");
        assertThat(line).doesNotContain(POLICY_ID).doesNotContain(ACTOR);
        assertThat(appender.list.get(0).getArgumentArray()).doesNotContain(POLICY_ID, 731904L, ACTOR);
    }

    @Test
    @DisplayName("NULL policy id and NULL collection still log without an identifier")
    void requestLogWithNulls() {
        when(service.setSplits(eq(null), eq(null), anyString())).thenReturn(0);

        ResponseEntity<Map<String, Object>> resp = controller.setSplits("null", new SetSplitsRequest(null, ACTOR));

        String correlationId = resp.getHeaders().getFirst(SplitsController.CORRELATION_HEADER);
        assertThat(appender.list.get(0).getFormattedMessage())
                .isEqualTo("POST /policies/{policyId}/splits correlation_id=" + correlationId + " agents=null");
    }

    @Test
    @DisplayName("each request gets its own correlation id")
    void correlationIdPerRequest() {
        String first = controller.setSplits("1", new SetSplitsRequest(null, ACTOR))
                .getHeaders().getFirst(SplitsController.CORRELATION_HEADER);
        String second = controller.setSplits("1", new SetSplitsRequest(null, ACTOR))
                .getHeaders().getFirst(SplitsController.CORRELATION_HEADER);
        assertThat(first).isNotEqualTo(second);
    }
}
