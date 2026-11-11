package com.halvergate.payments.packages.returns;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.server.ActiveMQServer;
import org.apache.activemq.artemis.core.server.ActiveMQServers;
import org.apache.activemq.artemis.core.server.Queue;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** Output-queue contract for HB.RETURN.POSTED, adapted from the pilot's status-queue readiness check. */
class ReturnsQueueContractTest {
    private static final String OUTPUT = "HB.RETURN.POSTED";
    private static final SimpleString NAME = SimpleString.of(OUTPUT);
    private ActiveMQServer broker;
    private ActiveMQConnectionFactory factory;

    @BeforeEach
    void start() throws Exception {
        var config = new ConfigurationImpl().setPersistenceEnabled(false).setSecurityEnabled(false)
            .setAddressQueueScanPeriod(20);
        config.addAcceptorConfiguration("in-vm", "vm://7");
        broker = ActiveMQServers.newActiveMQServer(config);
        broker.start();
        factory = new ActiveMQConnectionFactory("vm://7");
    }

    @AfterEach
    void stop() throws Exception {
        factory.close();
        broker.stop();
    }

    private void sendExisting(String body) throws Exception {
        try (var connection = factory.createConnection(); var session = connection.createSession()) {
            session.createProducer(session.createQueue(OUTPUT)).send(session.createTextMessage(body));
        }
    }

    private void assertRejectedUnchanged(Queue queue) throws Exception {
        var publisher = new ReturnsPublisher(factory, OUTPUT, 2_000);
        try {
            assertThatThrownBy(publisher::connect).isInstanceOf(IllegalStateException.class)
                .hasMessage(OUTPUT + " must be durable, non-auto-delete and ANYCAST");
        } finally {
            publisher.close();
        }
        assertThat(broker.locateQueue(NAME)).isSameAs(queue);
        assertThat(queue.getMessageCount()).isEqualTo(1L);
    }

    @Test
    void existingAutoDeleteQueueFailsReadinessWithoutDeletingOrDroppingMessages() throws Exception {
        var queue = broker.createQueue(QueueConfiguration.of(NAME).setRoutingType(RoutingType.ANYCAST)
            .setDurable(true).setAutoCreated(true).setAutoDelete(true).setAutoDeleteDelay(60_000L));
        sendExisting("pre-existing");
        assertRejectedUnchanged(queue);
        assertThat(queue.isAutoDelete()).isTrue();
    }

    @Test
    void existingAutoDeleteQueueWithConsumerFailsReadinessUnchanged() throws Exception {
        var queue = broker.createQueue(QueueConfiguration.of(NAME).setRoutingType(RoutingType.ANYCAST)
            .setDurable(true).setAutoCreated(true).setAutoDelete(true).setAutoDeleteDelay(0L));
        sendExisting("pre-existing");
        try (var connection = factory.createConnection(); var session = connection.createSession();
             var observer = session.createConsumer(session.createQueue(OUTPUT))) {
            assertRejectedUnchanged(queue);
            assertThat(queue.getConsumerCount()).isEqualTo(1);
        }
    }

    @Test
    void emptyAbandonedAutoDeleteQueueIsReapedByBrokerThenDeclaredDurable() throws Exception {
        var queue = broker.createQueue(QueueConfiguration.of(NAME).setRoutingType(RoutingType.ANYCAST)
            .setDurable(true).setAutoCreated(true).setAutoDelete(true).setAutoDeleteDelay(500L));
        try (var connection = factory.createConnection(); var session = connection.createSession()) {
            session.createConsumer(session.createQueue(OUTPUT)).close();
        }
        assertThat(broker.locateQueue(NAME)).isSameAs(queue);
        assertThat(queue.isAutoDelete()).isTrue();
        var publisher = new ReturnsPublisher(factory, OUTPUT, 5_000);
        try {
            publisher.connect();
        } finally {
            publisher.close();
        }
        var declared = broker.locateQueue(NAME);
        assertThat(declared).isNotSameAs(queue);
        assertThat(declared.isDurable()).isTrue();
        assertThat(declared.isAutoDelete()).isFalse();
        assertThat(declared.getRoutingType()).isEqualTo(RoutingType.ANYCAST);
    }

    @Test
    void emptyAutoDeleteQueueNotReapedWithinTimeoutFailsReadinessUnchanged() throws Exception {
        var queue = broker.createQueue(QueueConfiguration.of(NAME).setRoutingType(RoutingType.ANYCAST)
            .setDurable(true).setAutoCreated(true).setAutoDelete(true).setAutoDeleteDelay(60_000L));
        try (var connection = factory.createConnection(); var session = connection.createSession()) {
            session.createConsumer(session.createQueue(OUTPUT)).close();
        }
        var publisher = new ReturnsPublisher(factory, OUTPUT, 500);
        try {
            assertThatThrownBy(publisher::connect).isInstanceOf(IllegalStateException.class)
                .hasMessage(OUTPUT + " must be durable, non-auto-delete and ANYCAST");
        } finally {
            publisher.close();
        }
        assertThat(broker.locateQueue(NAME)).isSameAs(queue);
        assertThat(queue.isAutoDelete()).isTrue();
    }

    @Test
    void existingNonDurableQueueFailsReadinessWithoutDroppingMessages() throws Exception {
        var queue = broker.createQueue(QueueConfiguration.of(NAME).setRoutingType(RoutingType.ANYCAST)
            .setDurable(false).setAutoDelete(false));
        sendExisting("pre-existing");
        assertRejectedUnchanged(queue);
        assertThat(queue.isDurable()).isFalse();
    }

    @Test
    void existingCompatibleQueueIsReusedWithMessagesIntact() throws Exception {
        var queue = broker.createQueue(QueueConfiguration.of(NAME).setRoutingType(RoutingType.ANYCAST)
            .setDurable(true).setAutoCreated(false).setAutoDelete(false));
        sendExisting("pre-existing");
        var publisher = new ReturnsPublisher(factory, OUTPUT, 2_000);
        try {
            assertThat(publisher.connect().isClosed()).isFalse();
        } finally {
            publisher.close();
        }
        assertThat(broker.locateQueue(NAME)).isSameAs(queue);
        assertThat(queue.getMessageCount()).isEqualTo(1L);
    }

    @Test
    void absentQueueIsDeclaredDurableNonAutoDeleteAnycast() throws Exception {
        var publisher = new ReturnsPublisher(factory, OUTPUT, 2_000);
        try {
            publisher.connect();
        } finally {
            publisher.close();
        }
        var queue = broker.locateQueue(NAME);
        assertThat(queue.isDurable()).isTrue();
        assertThat(queue.isAutoDelete()).isFalse();
        assertThat(queue.getRoutingType()).isEqualTo(RoutingType.ANYCAST);
    }
}
