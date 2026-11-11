package com.halvergate.customeralerts.packages.alerts;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import java.nio.file.Path;
import java.util.Map;
import com.halvergate.customeralerts.runtime.OutputQueueDeclarer;
import com.halvergate.customeralerts.runtime.TransactionOutcomeLogger;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.server.embedded.EmbeddedActiveMQ;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.activemq.artemis.jms.client.ActiveMQXAConnectionFactory;
import org.apache.camel.impl.DefaultCamelContext;
import org.h2.jdbcx.JdbcDataSource;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.jta.JtaTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

class AlertTransactionTest {
    @Test
    void autoCommitInsertSurvivesJmsRollbackAndDuplicateIsNotIgnored() throws Exception {
        var source = new JdbcDataSource();
        source.setURL("jdbc:h2:mem:alerts;DB_CLOSE_DELAY=-1");
        var jdbc = new JdbcTemplate(source);
        jdbc.execute("CREATE TABLE dispute_cases (flow varchar, request_id varchar, account_id varchar,"
            + " amount decimal(18,2), currency varchar, status varchar, PRIMARY KEY(flow,request_id))");
        var routes = new AlertRoutes(source, mock(AlertPublisher.class), new TransactionOutcomeLogger(),
            mock(OutputQueueDeclarer.class));
        var record = new AlertRecord("id", "account", "USD", "12.30", "CARD_DISPUTE", "body", false);
        System.setProperty("com.arjuna.ats.arjuna.objectstore.objectStoreDir",
            Path.of("target/alerts-transaction-logs").toAbsolutePath().toString());
        var manager = new JtaTransactionManager(com.arjuna.ats.jta.UserTransaction.userTransaction(),
            com.arjuna.ats.jta.TransactionManager.transactionManager());
        new TransactionTemplate(manager).execute(status -> {
            routes.insert(AlertRoutes.FLOWS.getFirst(), record);
            status.setRollbackOnly();
            return null;
        });
        assertThat(jdbc.queryForObject("SELECT count(*) FROM dispute_cases", Integer.class)).isEqualTo(1);
        assertThatThrownBy(() -> routes.insert(AlertRoutes.FLOWS.getFirst(), record))
            .isInstanceOf(org.springframework.dao.DuplicateKeyException.class);
    }

    @Test
    void literalPersistentPublishCommitsAndRollsBack() throws Exception {
        var broker = new EmbeddedActiveMQ();
        broker.setConfiguration(new ConfigurationImpl().setPersistenceEnabled(false).setSecurityEnabled(false)
            .addAcceptorConfiguration("alerts", "vm://41"));
        broker.start();
        try (var factory = new ActiveMQXAConnectionFactory("vm://41");
             var connection = factory.createConnection();
             var session = connection.createSession();
             var context = new DefaultCamelContext()) {
            var core = ((ActiveMQSession) session).getCoreSession();
            core.createQueue(QueueConfiguration.of("ALERT.TEST").setAddress("ALERT.TEST")
                .setRoutingType(RoutingType.ANYCAST).setDurable(true));
            var manager = com.arjuna.ats.jta.TransactionManager.transactionManager();
            var publisher = new AlertPublisher(factory, manager);
            var exchange = new org.apache.camel.support.DefaultExchange(context);
            exchange.getMessage().setBody("receipt");
            exchange.getMessage().setHeaders(Map.of("requestId", "request", "accountId", "account",
                "JMSXGroupID", "account", "sequence", "2", "unwanted", "discard"));
            assertThatThrownBy(() -> publisher.publish(exchange, "ALERT.TEST"))
                .isInstanceOf(IllegalStateException.class);
            manager.begin();
            publisher.publish(exchange, "ALERT.TEST");
            manager.rollback();
            try (var consumer = core.createConsumer("ALERT.TEST")) {
                core.start();
                assertThat(consumer.receiveImmediate()).isNull();
                manager.begin();
                publisher.publish(exchange, "ALERT.TEST");
                manager.commit();
                var message = consumer.receive(2000);
                assertThat(message).isNotNull();
                assertThat(message.isDurable()).isTrue();
                assertThat(message.getStringProperty("JMSXGroupID")).isEqualTo("account");
                assertThat(message.getStringProperty("sequence")).isEqualTo("2");
                assertThat(message.containsProperty(SimpleString.of("unwanted"))).isFalse();
                assertThat(message.containsProperty(SimpleString.of("_AMQ_GROUP_ID"))).isFalse();
                assertThat(message.containsProperty(SimpleString.of("__AMQ_CID"))).isFalse();
            }
        } finally {
            broker.stop();
        }
    }

    @Test
    void unavailableDatabaseFailsReadiness() throws Exception {
        var source = new JdbcDataSource();
        source.setURL("jdbc:h2:invalid-url");
        var routes = new AlertRoutes(source, mock(AlertPublisher.class), new TransactionOutcomeLogger(),
            mock(OutputQueueDeclarer.class));
        try (var context = new DefaultCamelContext()) {
            assertThatThrownBy(() -> routes.beforeApplicationStart(context))
                .isInstanceOf(IllegalStateException.class).hasMessage("Alerts dependencies are not ready");
        }
    }
}
