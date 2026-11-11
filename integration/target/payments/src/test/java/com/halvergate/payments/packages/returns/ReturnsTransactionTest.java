package com.halvergate.payments.packages.returns;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.server.ActiveMQServer;
import org.apache.activemq.artemis.core.server.ActiveMQServers;
import org.apache.activemq.artemis.core.settings.impl.AddressSettings;
import org.apache.activemq.artemis.jms.client.ActiveMQConnection;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.activemq.artemis.reader.TextMessageUtil;
import org.apache.camel.CamelContext;
import org.apache.camel.component.jms.JmsConsumer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jms.connection.JmsTransactionManager;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

@SpringBootTest(properties = {
    "spring.artemis.broker-url=vm://0", "spring.artemis.embedded.enabled=false",
    "spring.artemis.user=unused", "spring.artemis.password=unused",
    "spring.datasource.xa.data-source-class-name=org.h2.jdbcx.JdbcDataSource",
    "spring.datasource.xa.properties.url=jdbc:h2:mem:payments;DB_CLOSE_DELAY=-1",
    "spring.datasource.xa.properties.user=sa", "spring.datasource.xa.properties.password=",
    "spring.datasource.url=jdbc:h2:mem:payments;DB_CLOSE_DELAY=-1",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "narayana.log-dir=target/transaction-logs",
    "camel.springboot.main-run-controller=false", "payments.tx-hold-ms=0"
})
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
class ReturnsTransactionTest {
    private static final String INPUT = "HB.PAYMENT.RETURNS";
    private static final String OUTPUT = "HB.RETURN.POSTED";
    private static final String DLQ = "HB.UNDLV";
    private final JdbcTemplate db = new JdbcTemplate(
        new DriverManagerDataSource("jdbc:h2:mem:payments;DB_CLOSE_DELAY=-1", "sa", ""));
    private final ListAppender<ILoggingEvent> events = new ListAppender<>();

    @Autowired CamelContext camel;
    @Autowired ActiveMQServer broker;
    @Autowired JmsTemplate jms;
    @Autowired Environment environment;
    @MockitoSpyBean ReturnsPublisher publisher;

    @TestConfiguration
    static class BrokerConfiguration {
        @Bean(destroyMethod = "stop")
        ActiveMQServer embeddedBroker() throws Exception {
            var config = new ConfigurationImpl().setPersistenceEnabled(false).setSecurityEnabled(false);
            config.addAcceptorConfiguration("in-vm", "vm://0");
            config.addAddressSetting("#", new AddressSettings()
                .setDeadLetterAddress(SimpleString.of(DLQ)).setMaxDeliveryAttempts(4).setRedeliveryDelay(10)
                .setDefaultAddressRoutingType(RoutingType.ANYCAST).setDefaultQueueRoutingType(RoutingType.ANYCAST));
            for (String queue : new String[]{"HB.PAYMENT.INSTRUCTIONS", "HB.PAYMENT.STATUS", DLQ, INPUT}) {
                config.addQueueConfiguration(QueueConfiguration.of(queue).setAddress(queue).setRoutingType(RoutingType.ANYCAST));
            }
            ActiveMQServer server = ActiveMQServers.newActiveMQServer(config);
            server.start();
            return server;
        }
    }

    @BeforeEach
    void reset() {
        db.execute("CREATE TABLE IF NOT EXISTS payment_returns (flow VARCHAR NOT NULL,request_id VARCHAR NOT NULL,"
            + "account_id VARCHAR NOT NULL,amount NUMERIC(18,2) NOT NULL,currency VARCHAR NOT NULL,"
            + "status VARCHAR NOT NULL,PRIMARY KEY(flow,request_id))");
        db.update("DELETE FROM payment_returns");
        jms.setReceiveTimeout(100);
        events.start();
        ((Logger) LoggerFactory.getLogger(PaymentReturnsRoute.class)).addAppender(events);
    }

    @AfterEach
    void detach() {
        ((Logger) LoggerFactory.getLogger(PaymentReturnsRoute.class)).detachAppender(events);
        events.stop();
    }

    @Test
    void packageOwnedPropertiesAndNonXaConsumerAreWired() throws Exception {
        assertThat(environment.getProperty("payments.returns.input-queue")).isEqualTo(INPUT);
        assertThat(environment.getProperty("payments.returns.output-queue")).isEqualTo(OUTPUT);
        var consumer = (JmsConsumer) camel.getRoute(ReturnsConfiguration.ROUTE_ID).getConsumer();
        var container = consumer.getListenerContainer();
        assertThat(container.isSessionTransacted()).isTrue();
        assertThat(((org.springframework.jms.listener.DefaultMessageListenerContainer) container).getCacheLevel())
            .isEqualTo(org.springframework.jms.listener.DefaultMessageListenerContainer.CACHE_NONE);
        assertThat(consumer.getEndpoint().getConfiguration().getOrCreateTransactionManager()).isInstanceOf(JmsTransactionManager.class);
        assertThat(consumer.getEndpoint().getConfiguration().getConnectionFactory())
            .isExactlyInstanceOf(ActiveMQConnectionFactory.class);
        assertThat(camel.getRouteController().getRouteStatus(ReturnsConfiguration.ROUTE_ID).isStarted()).isTrue();
    }

    @Test
    void corpusCasesPublishLiteralHeadersAndPersistRequestCurrency() throws Exception {
        JsonNode corpus = ReturnsTransformTest.corpus();
        send(0);
        send(1);
        await().atMost(Duration.ofSeconds(10)).untilAsserted(() ->
            assertThat(db.queryForObject("SELECT COUNT(*) FROM payment_returns", Integer.class)).isEqualTo(2));
        List<Map<String, Object>> rows = db.queryForList(
            "SELECT flow,request_id,account_id,amount,currency,status FROM payment_returns ORDER BY request_id");
        for (int i = 0; i < 2; i++) {
            JsonNode expected = corpus.path("expected").path("db").path("payment_returns").get(i);
            var row = rows.get(i);
            assertThat(row.get("FLOW")).isEqualTo(expected.path("flow").asText());
            assertThat(row.get("REQUEST_ID")).isEqualTo(expected.path("request_id").asText());
            assertThat(row.get("ACCOUNT_ID")).isEqualTo(expected.path("account_id").asText());
            assertThat(((BigDecimal) row.get("AMOUNT")).toPlainString()).isEqualTo(expected.path("amount").asText());
            assertThat(row.get("CURRENCY")).isEqualTo(expected.path("currency").asText());
            assertThat(row.get("STATUS")).isEqualTo(expected.path("status").asText());
        }
        try (var factory = new ActiveMQConnectionFactory("vm://0");
             var connection = factory.createConnection()) {
            var session = ((ActiveMQConnection) connection).getInitialSession();
            session.start();
            try (var consumer = session.createConsumer(OUTPUT)) {
                for (JsonNode expected : corpus.path("expected").path("messages")) {
                    var output = consumer.receive(5000);
                    assertThat(output).isNotNull();
                    assertThat(TextMessageUtil.readBodyText(output.getBodyBuffer()).toString())
                        .isEqualTo(expected.path("body").asText());
                    assertThat(output.isDurable()).isTrue();
                    assertThat(output.getPropertyNames().stream().map(Object::toString).toList())
                        .containsExactlyInAnyOrder("requestId", "accountId", "JMSXGroupID", "sequence");
                    expected.path("headers").fields().forEachRemaining(entry ->
                        assertThat(output.getStringProperty(entry.getKey())).isEqualTo(entry.getValue().asText()));
                    output.acknowledge();
                    session.commit();
                }
            }
        }
        var queue = broker.locateQueue(SimpleString.of(OUTPUT));
        assertThat(queue.isDurable()).isTrue();
        assertThat(queue.isAutoDelete()).isFalse();
        assertThat(jms.receive(DLQ)).isNull();
        await().atMost(Duration.ofSeconds(5)).until(() -> lines("outcome=COMMIT").size() == 2);
    }

    @Test
    void publishFailureAfterAutoCommitInsertKeepsRowAndDeadLettersWithoutOutput() throws Exception {
        doThrow(new IllegalStateException("injected publish failure")).when(publisher).publish(any());
        send(0);
        var deadLetter = awaitDead();
        await().atMost(Duration.ofSeconds(5)).until(() -> lines("outcome=ROLLBACK").size() == 4);
        assertThat(deadLetter.getStringProperty("requestId")).isEqualTo("payment-returns-01");
        assertThat(db.queryForList("SELECT request_id,amount FROM payment_returns")).hasSize(1);
        assertThat(lines("auto-commit inserted")).hasSize(1);
        assertThat(lines("receive requestId=payment-returns-01")).hasSize(4);
        assertThat(lines("outcome=ROLLBACK")).hasSize(4);
        assertThat(jms.receive(OUTPUT)).isNull();
    }

    @Test
    void existingKeyIsNotUpsertedAndDeadLetters() throws Exception {
        db.update("INSERT INTO payment_returns (flow,request_id,account_id,amount,currency,status) VALUES (?,?,?,?,?,?)",
            ReturnsConfiguration.ROUTE_ID, "payment-returns-01", "CHK-1042", new BigDecimal("1.00"), "USD", "PRIOR");
        send(0);
        var deadLetter = awaitDead();
        assertThat(deadLetter.getStringProperty("requestId")).isEqualTo("payment-returns-01");
        assertThat(db.queryForObject("SELECT status FROM payment_returns", String.class)).isEqualTo("PRIOR");
        assertThat(db.queryForObject("SELECT amount FROM payment_returns", BigDecimal.class)).isEqualByComparingTo("1.00");
        assertThat(lines("auto-commit inserted")).isEmpty();
        assertThat(jms.receive(OUTPUT)).isNull();
    }

    private jakarta.jms.Message awaitDead() {
        jms.setReceiveTimeout(10000);
        var message = jms.receive(DLQ);
        jms.setReceiveTimeout(100);
        assertThat(message).isNotNull();
        return message;
    }

    private List<String> lines(String fragment) {
        return events.list.stream().map(ILoggingEvent::getFormattedMessage).filter(line -> line.contains(fragment)).toList();
    }

    private void send(int index) throws Exception {
        JsonNode input = ReturnsTransformTest.corpus().path("inputs").path("messages").get(index);
        jms.send(INPUT, session -> {
            var message = session.createTextMessage(input.path("body").asText());
            input.path("properties").fields().forEachRemaining(entry -> {
                try {
                    message.setStringProperty(entry.getKey(), entry.getValue().asText());
                } catch (Exception e) {
                    throw new IllegalStateException(e);
                }
            });
            return message;
        });
    }
}
