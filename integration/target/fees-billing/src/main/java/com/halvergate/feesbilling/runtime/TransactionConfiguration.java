package com.halvergate.feesbilling.runtime;

import javax.sql.DataSource;
import jakarta.jms.ConnectionFactory;
import org.apache.camel.component.jms.JmsComponent;
import org.apache.camel.spring.spi.SpringTransactionPolicy;
import org.postgresql.ds.PGSimpleDataSource;
import org.postgresql.xa.PGXADataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.jdbc.XADataSourceWrapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.PropertySource;
import org.springframework.transaction.jta.JtaTransactionManager;

@Configuration
@PropertySource(value = "classpath*:packages/*/package.yaml",
    factory = PackageYamlFactory.class, ignoreResourceNotFound = true)
public class TransactionConfiguration {
    @Bean
    @Primary
    DataSource dataSource(XADataSourceWrapper wrapper,
            @Value("${spring.datasource.url}") String url,
            @Value("${spring.datasource.username}") String user,
            @Value("${spring.datasource.password}") String password) throws Exception {
        PGXADataSource xa = new PGXADataSource();
        xa.setUrl(url);
        xa.setUser(user);
        xa.setPassword(password);
        return wrapper.wrapDataSource(xa);
    }

    @Bean
    DataSource autoCommitDataSource(@Value("${spring.datasource.url}") String url,
            @Value("${spring.datasource.username}") String user,
            @Value("${spring.datasource.password}") String password) {
        PGSimpleDataSource source = new PGSimpleDataSource();
        source.setUrl(url);
        source.setUser(user);
        source.setPassword(password);
        return source;
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

    @Bean
    org.apache.camel.builder.RouteConfigurationBuilder brokerRedelivery() {
        return new org.apache.camel.builder.RouteConfigurationBuilder() {
            @Override
            public void configuration() {
                routeConfiguration().errorHandler(new org.apache.camel.builder.SpringTransactionErrorHandlerBuilder()
                    .maximumRedeliveries(0));
            }
        };
    }

    @Bean
    org.apache.camel.spring.boot.CamelContextConfiguration outputQueueReadiness(OutputQueueDeclarer queues) {
        return new org.apache.camel.spring.boot.CamelContextConfiguration() {
            @Override
            public void beforeApplicationStart(org.apache.camel.CamelContext context) {
                try {
                    queues.declare();
                } catch (Exception e) {
                    throw new IllegalStateException("Output destinations are not ready", e);
                }
            }

            @Override
            public void afterApplicationStart(org.apache.camel.CamelContext context) { }
        };
    }
}
