package com.halvergate.payments;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

import java.time.Duration;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.jms.Message;
import javax.sql.DataSource;
import javax.transaction.xa.XAResource;
import com.arjuna.ats.internal.jta.recovery.arjunacore.XARecoveryModule;
import com.arjuna.ats.jta.xa.XidImple;
import com.arjuna.ats.arjuna.common.Uid;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.test.util.ReflectionTestUtils;
import org.apache.activemq.artemis.jms.client.ActiveMQXAConnectionFactory;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.server.ActiveMQServer;
import org.apache.activemq.artemis.core.server.ActiveMQServers;
import org.apache.activemq.artemis.core.settings.impl.AddressSettings;
import org.apache.camel.CamelContext;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.activemq.artemis.reader.TextMessageUtil;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.jta.JtaTransactionManager;
import org.springframework.test.annotation.DirtiesContext;
import org.slf4j.LoggerFactory;

@SpringBootTest(properties = {
    "spring.artemis.broker-url=vm://0", "spring.artemis.embedded.enabled=false",
    "spring.artemis.user=unused", "spring.artemis.password=unused",
    "spring.datasource.xa.data-source-class-name=org.h2.jdbcx.JdbcDataSource",
    "spring.datasource.xa.properties.url=jdbc:h2:mem:payments;DB_CLOSE_DELAY=-1",
    "spring.datasource.xa.properties.user=sa", "spring.datasource.xa.properties.password=",
    "spring.datasource.password=", "narayana.log-dir=target/transaction-logs",
    "camel.springboot.main-run-controller=false", "payments.tx-hold-ms=150"
})
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
class InstructionTransactionTest {
    @Autowired JdbcTemplate jdbc;
    @Autowired JmsTemplate jms;
    @Autowired CamelContext camel;
    @Autowired JtaTransactionManager transactionManager;
    @Autowired DataSource dataSource;
    @Autowired ActiveMQServer broker;
    @Autowired XaStatusPublisher publisher;
    @Autowired StatusXaRecovery recovery;
    @Autowired XARecoveryModule recoveryModule;
    @Autowired @Qualifier("nonXaJmsConnectionFactory") ActiveMQXAConnectionFactory rawFactory;
    private final ListAppender<ILoggingEvent> events = new ListAppender<>();
    private final ListAppender<ILoggingEvent> xaEvents = new ListAppender<>();

    @TestConfiguration
    static class BrokerConfiguration {
        @Bean(destroyMethod = "stop")
        ActiveMQServer embeddedBroker() throws Exception {
            var config = new ConfigurationImpl().setPersistenceEnabled(false).setSecurityEnabled(false)
                .setAddressQueueScanPeriod(20);
            config.addAcceptorConfiguration("in-vm", "vm://0");
            config.addAddressSetting("#", new AddressSettings()
                .setDeadLetterAddress(SimpleString.of("HB.UNDLV")).setMaxDeliveryAttempts(4).setRedeliveryDelay(10)
                .setDefaultAddressRoutingType(RoutingType.ANYCAST).setDefaultQueueRoutingType(RoutingType.ANYCAST));
            config.addAddressSetting("HB.PAYMENT.STATUS", new AddressSettings()
                .setAutoDeleteQueues(false).setAutoDeleteAddresses(false));
            for (String queue : new String[]{"HB.PAYMENT.INSTRUCTIONS", "HB.PAYMENT.STATUS", "HB.UNDLV"}) {
                config.addQueueConfiguration(QueueConfiguration.of(queue).setAddress(queue).setRoutingType(RoutingType.ANYCAST));
            }
            ActiveMQServer server = ActiveMQServers.newActiveMQServer(config);
            server.start();
            return server;
        }
    }

    @BeforeEach
    void reset() throws Exception {
        var consumer = (org.apache.camel.component.jms.JmsConsumer) camel.getRoute("payments.instruction-intake").getConsumer();
        assertThat(consumer.getListenerContainer().isExposeListenerSession()).isTrue();
        jms.setReceiveTimeout(100);
        for (String queue : new String[]{"HB.PAYMENT.STATUS", "HB.UNDLV"}) {
            while (jms.receive(queue) != null) { }
        }
        for (String table : new String[]{"payment_inbox", "payment_ledger"}) {
            jdbc.execute("CREATE TABLE IF NOT EXISTS " + table
                + " (flow VARCHAR NOT NULL,request_id VARCHAR NOT NULL,account_id VARCHAR NOT NULL,"
                + "amount NUMERIC(18,2) NOT NULL,currency VARCHAR NOT NULL,status VARCHAR NOT NULL,PRIMARY KEY(flow,request_id))");
            jdbc.update("DELETE FROM " + table);
        }
        events.start();
        ((Logger) LoggerFactory.getLogger(InstructionIntakeRoute.class)).addAppender(events);
        xaEvents.start();
        ((Logger) LoggerFactory.getLogger("com.arjuna.ats")).addAppender(xaEvents);
    }

    @AfterEach
    void detachLog() {
        ((Logger) LoggerFactory.getLogger(InstructionIntakeRoute.class)).detachAppender(events);
        events.stop();
        ((Logger) LoggerFactory.getLogger("com.arjuna.ats")).detachAppender(xaEvents);
        xaEvents.stop();
        assertThat(xaEvents.list.stream().map(ILoggingEvent::getFormattedMessage).toList())
            .noneMatch(line -> line.contains("XAER_PROTO") || line.contains("ARJUNA016129"));
    }

    @Test
    void configuredQueueSurvivesEmptySubscriberDisconnect() throws Exception {
        var core = ((org.apache.activemq.artemis.jms.client.ActiveMQConnection) publisher.connect()).getInitialSession();
        var queue = core.queueQuery(SimpleString.of("HB.PAYMENT.STATUS"));
        assertThat(queue.isDurable()).isTrue();
        assertThat(queue.isAutoDelete()).isFalse();
        assertThat(queue.getRoutingType()).isEqualTo(RoutingType.ANYCAST);
        try (var factory = new ActiveMQConnectionFactory("vm://0");
             var connection = factory.createConnection();
             var session = connection.createSession();
             var subscriber = session.createConsumer(session.createQueue("HB.PAYMENT.STATUS"))) {
            connection.start();
            assertThat(subscriber.receiveNoWait()).isNull();
        }
        await().during(Duration.ofMillis(250)).atMost(Duration.ofSeconds(2)).untilAsserted(() -> {
            assertThat(core.queueQuery(SimpleString.of("HB.PAYMENT.STATUS")).isExists()).isTrue();
            assertThat(broker.locateQueue(SimpleString.of("HB.PAYMENT.STATUS")).getConsumerCount()).isZero();
        });
    }

    private void sendFirstInput() throws Exception {
        sendInput(0);
    }

    @Test
    void registeredHelperRecoversAndCommitsPreparedSendAfterOriginalConnectionCloses() throws Exception {
        assertThat((java.util.Set<?>) ReflectionTestUtils.getField(recoveryModule, "_xaResourceRecoveryHelpers"))
            .anyMatch(helper -> helper == recovery)
            .anyMatch(helper -> helper.getClass().getName().contains("DataSourceXAResourceRecoveryHelper"));
        var xid = new XidImple(new Uid());
        try (var connection = rawFactory.createXAConnection(); var session = connection.createXASession()) {
            var resource = session.getXAResource();
            resource.start(xid, XAResource.TMNOFLAGS);
            try (var producer = session.createProducer(session.createQueue("HB.PAYMENT.STATUS"))) {
                producer.send(session.createTextMessage("prepared status"));
            }
            resource.end(xid, XAResource.TMSUCCESS);
            assertThat(resource.prepare(xid)).isEqualTo(XAResource.XA_OK);
        }
        assertThat(broker.locateQueue(SimpleString.of("HB.PAYMENT.STATUS")).getMessageCount()).isZero();
        var resource = recovery.getXAResources()[0];
        var recovered = resource.recover(XAResource.TMSTARTRSCAN);
        resource.recover(XAResource.TMENDRSCAN);
        assertThat(recovered).anySatisfy(branch -> {
            assertThat(branch.getFormatId()).isEqualTo(xid.getFormatId());
            assertThat(branch.getGlobalTransactionId()).isEqualTo(xid.getGlobalTransactionId());
            assertThat(branch.getBranchQualifier()).isEqualTo(xid.getBranchQualifier());
        });
        resource.commit(xid, false);
        assertThat(jms.receiveAndConvert("HB.PAYMENT.STATUS")).isEqualTo("prepared status");
        assertThat(resource.recover(XAResource.TMSTARTRSCAN)).isEmpty();
        resource.recover(XAResource.TMENDRSCAN);
        recovery.close();
        assertThat((java.util.Set<?>) ReflectionTestUtils.getField(recoveryModule, "_xaResourceRecoveryHelpers"))
            .noneMatch(helper -> helper == recovery);
    }

    private void sendInput(int index) throws Exception {
        JsonNode input = InstructionTransformTest.corpus().path("inputs").path("messages").get(index);
        jms.send("HB.PAYMENT.INSTRUCTIONS", session -> {
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

    @Test
    void commitsBothRowsAndOnePersistentOutputPerInputAndHoldsOnlyFirstTransaction() throws Exception {
        assertThat(transactionManager.getTransactionManager()).isNotNull();
        assertThat(dataSource.getClass().getName()).contains("Narayana");
        sendFirstInput();
        sendInput(1);
        await().atMost(Duration.ofSeconds(15)).untilAsserted(() -> {
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM payment_inbox", Integer.class)).isEqualTo(2);
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM payment_ledger", Integer.class)).isEqualTo(2);
        });
        try (var factory = new ActiveMQConnectionFactory("vm://0");
             var connection = factory.createConnection()) {
            var session = ((org.apache.activemq.artemis.jms.client.ActiveMQConnection) connection).getInitialSession();
            session.start();
            try (var consumer = session.createConsumer("HB.PAYMENT.STATUS")) {
                for (JsonNode expected : InstructionTransformTest.corpus().path("expected").path("messages")) {
                    var output = consumer.receive(1000);
                    assertThat(output).isNotNull();
                    assertThat(TextMessageUtil.readBodyText(output.getBodyBuffer()).toString()).isEqualTo(expected.path("body").asText());
                    assertThat(output.isDurable()).isTrue();
                    assertThat(output.getRoutingType()).isNull();
                    assertThat(output.getPropertyNames().stream().map(Object::toString).toList())
                        .containsExactlyInAnyOrder("requestId", "accountId", "JMSXGroupID", "sequence");
                    expected.path("headers").fields().forEachRemaining(entry ->
                        assertThat(output.getStringProperty(entry.getKey())).isEqualTo(entry.getValue().asText()));
                    output.acknowledge();
                    session.commit();
                }
            }
        }
        assertThat(jms.receive("HB.PAYMENT.STATUS")).isNull();
        assertThat(jms.receive("HB.UNDLV")).isNull();
        assertThat(broker.locateQueue(SimpleString.of("HB.PAYMENT.STATUS")).isAutoDelete()).isFalse();
        assertThat(events.list.stream().map(ILoggingEvent::getFormattedMessage)
            .filter(line -> line.startsWith("in-tx hold")).toList())
            .singleElement().asString().contains("requestId=instruction-intake-01");
    }

    @Test
    void ledgerFailureRollsBackInboxAndOutputAndDeadLettersAfterFourDeliveries() throws Exception {
        jdbc.update("INSERT INTO payment_ledger VALUES (?,?,?,?,?,?)",
            "payments.instruction-intake", "instruction-intake-01", "conflict", 1, "USD", "EXISTING");
        sendFirstInput();
        jms.setReceiveTimeout(15000);
        Message dead = jms.receive("HB.UNDLV");
        assertThat(dead).isNotNull();
        assertThat(dead.getStringProperty("requestId")).isEqualTo("instruction-intake-01");
        assertThat(dead.getIntProperty("JMSXDeliveryCount")).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM payment_inbox", Integer.class)).isZero();
        assertThat(jdbc.queryForObject("SELECT account_id FROM payment_ledger", String.class)).isEqualTo("conflict");
        jms.setReceiveTimeout(100);
        assertThat(jms.receive("HB.PAYMENT.STATUS")).isNull();
        assertThat(events.list.stream().map(ILoggingEvent::getFormattedMessage)
            .filter(line -> line.startsWith("in-tx receive")).toList())
            .hasSize(4).satisfies(lines -> {
                for (int i = 0; i < 4; i++) {
                    assertThat(lines.get(i)).contains("deliveryCount=" + (i + 1));
                }
            });
    }

    @Test
    void emptyBodyRollsBackAndDeadLettersWithoutPosting() {
        jms.send("HB.PAYMENT.INSTRUCTIONS", session -> session.createTextMessage(""));
        jms.setReceiveTimeout(15000);
        assertThat(jms.receive("HB.UNDLV")).isNotNull();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM payment_inbox", Integer.class)).isZero();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM payment_ledger", Integer.class)).isZero();
        jms.setReceiveTimeout(100);
        assertThat(jms.receive("HB.PAYMENT.STATUS")).isNull();
        assertThat(events.list.stream().map(ILoggingEvent::getFormattedMessage)
            .filter(line -> line.startsWith("in-tx receive")).toList()).hasSize(4);
    }
}
