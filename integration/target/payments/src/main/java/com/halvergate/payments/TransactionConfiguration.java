package com.halvergate.payments;

import jakarta.jms.ConnectionFactory;
import org.apache.camel.component.jms.JmsComponent;
import org.apache.camel.spring.spi.SpringTransactionPolicy;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.jta.JtaTransactionManager;
import org.springframework.jdbc.core.JdbcTemplate;
import org.apache.camel.CamelContext;
import org.apache.camel.spring.boot.CamelContextConfiguration;
import org.apache.camel.component.jms.DefaultJmsMessageListenerContainer;
import org.apache.camel.component.jms.MessageListenerContainerFactory;
import jakarta.jms.Message;
import jakarta.jms.MessageConsumer;
import jakarta.jms.JMSException;
import com.arjuna.ats.arjuna.common.arjPropertyManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Configuration
public class TransactionConfiguration {
    private static final Logger LOG = LoggerFactory.getLogger(TransactionConfiguration.class);
    @Bean
    CamelContextConfiguration paymentsReadiness(JdbcTemplate jdbc, XaStatusPublisher publisher) {
        return new CamelContextConfiguration() {
            @Override
            public void beforeApplicationStart(CamelContext context) {
                try {
                    jdbc.queryForObject("SELECT 1", Integer.class);
                    publisher.connect();
                    LOG.info("Narayana node identifier={}", arjPropertyManager.getCoreEnvironmentBean().getNodeIdentifier());
                } catch (Exception e) {
                    throw new IllegalStateException("Payment resources are not ready", e);
                }
            }

            @Override
            public void afterApplicationStart(CamelContext context) {
                try (var template = context.createProducerTemplate()) {
                    template.requestBody("xslt-saxon:Transforms/payment-status.xsl?output=DOM", "<request/>");
                    context.getRouteController().startRoute("payments.instruction-intake");
                } catch (Exception e) {
                    throw new IllegalStateException("Payment route is not ready", e);
                }
            }
        };
    }

    @Bean
    MessageListenerContainerFactory paymentsListener(JdbcTemplate jdbc, XaStatusPublisher publisher) {
        return endpoint -> new DefaultJmsMessageListenerContainer(endpoint) {
            @Override
            protected Message receiveMessage(MessageConsumer consumer) throws JMSException {
                try {
                    jdbc.queryForObject("SELECT 1", Integer.class);
                    publisher.prepare();
                } catch (Exception e) {
                    var failure = new JMSException("Could not enlist payment resources before receive");
                    failure.initCause(e);
                    throw failure;
                }
                return super.receiveMessage(consumer);
            }
        };
    }

    @Bean
    JmsComponent jms(ConnectionFactory connectionFactory, JtaTransactionManager transactionManager) {
        JmsComponent component = JmsComponent.jmsComponentTransacted(connectionFactory, transactionManager);
        component.setCacheLevelName("CACHE_NONE");
        component.setConcurrentConsumers(1);
        component.setDeliveryPersistent(true);
        component.setRecoveryInterval(100);
        component.setExposeListenerSession(true);
        return component;
    }

    @Bean
    SpringTransactionPolicy required(JtaTransactionManager transactionManager) {
        SpringTransactionPolicy policy = new SpringTransactionPolicy(transactionManager);
        policy.setPropagationBehaviorName("PROPAGATION_REQUIRED");
        return policy;
    }
}
