package com.halvergate.payments;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.awaitility.Awaitility.await;
import static org.mockito.Mockito.mock;

import jakarta.transaction.TransactionManager;
import java.nio.file.Path;
import java.time.Duration;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.config.FileDeploymentManager;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.config.impl.FileConfiguration;
import org.apache.activemq.artemis.core.server.ActiveMQServers;
import org.apache.activemq.artemis.core.settings.impl.AddressSettings;
import org.apache.activemq.artemis.jms.client.ActiveMQXAConnectionFactory;
import org.junit.jupiter.api.Test;

class StatusQueueConfigurationTest {
    @Test
    void fixtureXmlPassesArtemisSchemaAndDeclaresDurableAnycastStatusQueue() throws Exception {
        var config = new FileConfiguration();
        new FileDeploymentManager(Path.of("../../fixture/broker.xml").toUri().toString())
            .addDeployable(config).readConfiguration();
        assertThat(config.isParsed()).isTrue();
        assertThat(config.getAddressConfigurations()).anySatisfy(address -> {
            assertThat(address.getName()).isEqualTo("HB.PAYMENT.STATUS");
            assertThat(address.getQueueConfigs()).anySatisfy(queue -> {
                assertThat(queue.getName().toString()).isEqualTo("HB.PAYMENT.STATUS");
                assertThat(queue.isDurable()).isTrue();
                assertThat(queue.getRoutingType()).isEqualTo(RoutingType.ANYCAST);
            });
        });
        var settings = config.getAddressSettings().get("HB.PAYMENT.STATUS");
        assertThat(settings.isAutoDeleteQueues()).isFalse();
        assertThat(settings.isAutoDeleteAddresses()).isFalse();
    }

    @Test
    void addressSettingsDoNotRescueExistingAutoDeleteQueueAndPublisherFailsBeforeConsuming() throws Exception {
        var config = new ConfigurationImpl().setPersistenceEnabled(false).setSecurityEnabled(false)
            .setAddressQueueScanPeriod(20);
        config.addAcceptorConfiguration("in-vm", "vm://1");
        config.addAddressSetting("HB.PAYMENT.STATUS", new AddressSettings()
            .setAutoDeleteQueues(false).setAutoDeleteAddresses(false));
        var broker = ActiveMQServers.newActiveMQServer(config);
        broker.start();
        try (var factory = new ActiveMQXAConnectionFactory("vm://1")) {
            var name = SimpleString.of("HB.PAYMENT.STATUS");
            var queue = broker.createQueue(QueueConfiguration.of(name).setRoutingType(RoutingType.ANYCAST)
                .setDurable(true).setAutoCreated(true).setAutoDelete(true).setAutoDeleteDelay(0L));
            try (var connection = factory.createConnection();
                 var session = connection.createSession();
                 var subscriber = session.createConsumer(session.createQueue(name.toString()))) {
                connection.start();
                assertThat(subscriber.receiveNoWait()).isNull();
                var publisher = new XaStatusPublisher(factory, mock(TransactionManager.class), 0);
                try {
                    assertThatThrownBy(publisher::connect).isInstanceOf(IllegalStateException.class)
                        .hasMessage("HB.PAYMENT.STATUS must be durable, non-auto-delete and ANYCAST");
                    assertThat(broker.locateQueue(name)).isSameAs(queue);
                    assertThat(queue.isAutoDelete()).isTrue();
                } finally {
                    publisher.close();
                }
            }
            await().atMost(Duration.ofSeconds(3)).untilAsserted(() -> assertThat(broker.locateQueue(name)).isNull());
            System.out.println("Existing autoDelete=true queue was removed after empty disconnect despite address settings; publisher rejected it");
        } finally {
            broker.stop();
        }
    }
}
