package com.halvergate.feesbilling.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import java.util.List;
import java.util.Map;
import jakarta.jms.ConnectionFactory;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.server.embedded.EmbeddedActiveMQ;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.support.EncodedResource;
import org.springframework.transaction.jta.JtaTransactionManager;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

class RuntimeTest {
    @Test
    void jmsUsesBrokerRetriesAndJta() {
        var configuration = new TransactionConfiguration();
        var jms = configuration.jms(mock(ConnectionFactory.class), mock(JtaTransactionManager.class));
        assertThat(jms.getConfiguration().isTransacted()).isTrue();
        assertThat(jms.getConfiguration().getCacheLevelName()).isEqualTo("CACHE_NONE");
        assertThat(jms.getConfiguration().getRecoveryInterval()).isEqualTo(100);
        assertThat(jms.getConfiguration().isExposeListenerSession()).isTrue();
        assertThat(jms.getConfiguration().isDeliveryPersistent()).isTrue();
    }

    @Test
    void noDestinationsDoesNotConnect() throws Exception {
        var factory = mock(ConnectionFactory.class);
        new OutputQueueDeclarer(factory, new OutputQueueDeclarer.Destinations()).declare();
        verifyNoInteractions(factory);
    }

    @Test
    void declaresDurableOutputIdempotently() throws Exception {
        var broker = new EmbeddedActiveMQ();
        broker.setConfiguration(new ConfigurationImpl().setPersistenceEnabled(false)
            .setSecurityEnabled(false).addAcceptorConfiguration("invm", "vm://0"));
        broker.start();
        try (var factory = new ActiveMQConnectionFactory("vm://0")) {
            var destinations = new OutputQueueDeclarer.Destinations();
            destinations.setOutputQueues(Map.of("first", List.of("OUTPUT"), "second", List.of("OTHER", "OUTPUT")));
            var declarer = new OutputQueueDeclarer(factory, destinations);
            declarer.declare();
            declarer.declare();
            try (var connection = factory.createConnection();
                 var session = connection.createSession()) {
                var query = ((ActiveMQSession) session).getCoreSession()
                    .queueQuery(SimpleString.of("OUTPUT"));
                assertThat(query.isExists()).isTrue();
                assertThat(query.isDurable()).isTrue();
                assertThat(((ActiveMQSession) session).getCoreSession()
                    .queueQuery(SimpleString.of("OTHER")).isDurable()).isTrue();
            }
        } finally {
            broker.stop();
        }
    }

    @Test
    void unavailableBrokerFailsReadiness() throws Exception {
        var factory = mock(ConnectionFactory.class);
        var destinations = new OutputQueueDeclarer.Destinations();
        destinations.setOutputQueues(Map.of("test", List.of("OUTPUT")));
        org.mockito.Mockito.when(factory.createConnection())
            .thenThrow(new IllegalStateException("unavailable"));
        assertThatThrownBy(() -> new OutputQueueDeclarer(factory, destinations).declare())
            .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void yamlLoadsNestedPackageProperties() throws Exception {
        var resource = new ByteArrayResource("alerts:\n  enabled: true\n".getBytes());
        var properties = new PackageYamlFactory().createPropertySource(null, new EncodedResource(resource));
        assertThat(properties.getProperty("alerts.enabled")).isEqualTo(true);
    }

    @Test
    void transactionOutcomeRequiresAndRegistersSynchronization() {
        var logger = new TransactionOutcomeLogger();
        assertThatThrownBy(() -> logger.register("missing")).isInstanceOf(IllegalStateException.class);
        TransactionSynchronizationManager.initSynchronization();
        try {
            logger.register("request");
            var callbacks = TransactionSynchronizationManager.getSynchronizations();
            assertThat(callbacks).hasSize(1);
            callbacks.getFirst().afterCompletion(TransactionSynchronization.STATUS_COMMITTED);
            callbacks.getFirst().afterCompletion(TransactionSynchronization.STATUS_ROLLED_BACK);
        } finally {
            TransactionSynchronizationManager.clearSynchronization();
        }
    }
}
