package com.halvergate.payments.packages.returns;

import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.camel.CamelContext;
import org.apache.camel.component.jms.JmsComponent;
import org.apache.camel.spring.boot.CamelContextConfiguration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;

/**
 * Package-local wiring for payments.payment-returns. The legacy process is AUTO_COMMIT, so this
 * package uses its own non-XA broker and database resources and never joins the module's JTA manager.
 * It reads the module's existing connection settings (read-only) rather than adding shared config.
 */
@Configuration(proxyBeanMethods = false)
@PropertySource("classpath:packages/returns/returns.properties")
public class ReturnsConfiguration {
    public static final String ROUTE_ID = "payments.payment-returns";

    @Bean(destroyMethod = "close")
    ReturnsLedger returnsLedger(@Value("${spring.datasource.xa.properties.url:${spring.datasource.url}}") String url,
                                @Value("${spring.datasource.xa.properties.user:${spring.datasource.username:}}") String user,
                                @Value("${spring.datasource.xa.properties.password:${spring.datasource.password:}}") String password) {
        return new ReturnsLedger(url, user, password);
    }

    @Bean(destroyMethod = "close")
    ReturnsPublisher returnsPublisher(@Value("${spring.artemis.broker-url}") String brokerUrl,
                                      @Value("${spring.artemis.user:}") String user,
                                      @Value("${spring.artemis.password:}") String password,
                                      @Value("${payments.returns.output-queue}") String outputQueue) {
        return new ReturnsPublisher(new ActiveMQConnectionFactory(brokerUrl, user, password), outputQueue);
    }

    /** Holds the consumer factory without exposing a second ConnectionFactory bean to the module. */
    public record ReturnsBroker(ActiveMQConnectionFactory consumerFactory) implements AutoCloseable {
        @Override
        public void close() {
            consumerFactory.close();
        }
    }

    @Bean(destroyMethod = "close")
    ReturnsBroker returnsBroker(@Value("${spring.artemis.broker-url}") String brokerUrl,
                                                               @Value("${spring.artemis.user:}") String user,
                                                               @Value("${spring.artemis.password:}") String password) {
        return new ReturnsBroker(new ActiveMQConnectionFactory(brokerUrl, user, password));
    }

    @Bean("returnsJms")
    JmsComponent returnsJms(ReturnsBroker broker) {
        ActiveMQConnectionFactory factory = broker.consumerFactory();
        JmsComponent component = new JmsComponent();
        component.setConnectionFactory(factory);
        component.setTransacted(true);
        return component;
    }

    @Bean
    CamelContextConfiguration returnsReadiness(ReturnsLedger ledger, ReturnsPublisher publisher,
                                               @Value("${payments.returns.stylesheet}") String stylesheet) {
        return new CamelContextConfiguration() {
            @Override
            public void beforeApplicationStart(CamelContext context) {
                try {
                    ledger.ping();
                    publisher.connect();
                } catch (Exception e) {
                    throw new IllegalStateException("payment-returns resources are not ready", e);
                }
            }

            @Override
            public void afterApplicationStart(CamelContext context) {
                try (var template = context.createProducerTemplate()) {
                    template.requestBody("xslt-saxon:" + stylesheet + "?output=DOM", "<request/>");
                    context.getRouteController().startRoute(ROUTE_ID);
                } catch (Exception e) {
                    throw new IllegalStateException("payment-returns route did not start", e);
                }
            }
        };
    }
}
