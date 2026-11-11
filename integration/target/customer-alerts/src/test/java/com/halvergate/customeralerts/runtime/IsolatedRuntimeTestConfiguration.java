package com.halvergate.customeralerts.runtime;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import javax.sql.DataSource;
import jakarta.jms.ConnectionFactory;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.server.embedded.EmbeddedActiveMQ;
import org.apache.activemq.artemis.jms.client.ActiveMQXAConnectionFactory;
import org.h2.jdbcx.JdbcDataSource;
import org.springframework.beans.factory.config.BeanFactoryPostProcessor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.support.AbstractBeanDefinition;
import org.springframework.boot.jdbc.XADataSourceWrapper;
import org.springframework.boot.jms.XAConnectionFactoryWrapper;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;

@TestConfiguration(proxyBeanMethods = false)
public class IsolatedRuntimeTestConfiguration {
    private static final AtomicInteger BROKER_IDS = new AtomicInteger(1000);

    @Bean
    static BeanFactoryPostProcessor isolatedRuntime(ConfigurableEnvironment environment) {
        environment.getPropertySources().addFirst(new MapPropertySource("isolated-runtime", Map.of(
            "spring.artemis.mode", "native",
            "spring.artemis.broker-url", "vm://" + BROKER_IDS.incrementAndGet(),
            "spring.artemis.user", "test",
            "spring.artemis.password", "test")));
        String database = UUID.randomUUID().toString();
        return beans -> {
            var xa = (AbstractBeanDefinition) beans.getBeanDefinition("dataSource");
            xa.setInstanceSupplier(() -> {
                try {
                    return beans.getBean(XADataSourceWrapper.class).wrapDataSource(database(database + "-xa"));
                } catch (Exception e) {
                    throw new IllegalStateException("Cannot create isolated XA datasource", e);
                }
            });
            var autoCommit = (AbstractBeanDefinition) beans.getBeanDefinition("autoCommitDataSource");
            autoCommit.setInstanceSupplier(() -> database(database + "-autocommit"));
        };
    }

    private static JdbcDataSource database(String name) {
        JdbcDataSource source = new JdbcDataSource();
        source.setURL("jdbc:h2:mem:" + name + ";MODE=PostgreSQL;DB_CLOSE_DELAY=-1");
        Path directory = Path.of("").toAbsolutePath();
        while (directory != null) {
            Path schema = directory.resolve("integration/legacy-bw6/Database/schema.sql");
            if (Files.isRegularFile(schema)) {
                new ResourceDatabasePopulator(new FileSystemResource(schema)).execute(source);
                return source;
            }
            directory = directory.getParent();
        }
        throw new IllegalStateException("Cannot find frozen integration database schema");
    }

    @Bean(initMethod = "start", destroyMethod = "stop")
    EmbeddedActiveMQ isolatedTestBroker(ConfigurableEnvironment environment) throws Exception {
        var broker = new EmbeddedActiveMQ();
        broker.setConfiguration(new ConfigurationImpl().setPersistenceEnabled(false).setSecurityEnabled(false)
            .addAcceptorConfiguration("invm", environment.getRequiredProperty("spring.artemis.broker-url")));
        return broker;
    }

    @Bean
    @Primary
    ConnectionFactory jmsConnectionFactory(
            @Qualifier("nonXaJmsConnectionFactory") ActiveMQXAConnectionFactory nativeFactory,
            XAConnectionFactoryWrapper wrapper) throws Exception {
        return wrapper.wrapConnectionFactory(nativeFactory);
    }

    @Bean(destroyMethod = "close")
    ActiveMQXAConnectionFactory nonXaJmsConnectionFactory(EmbeddedActiveMQ isolatedTestBroker,
            ConfigurableEnvironment environment) {
        return new ActiveMQXAConnectionFactory(environment.getRequiredProperty("spring.artemis.broker-url"));
    }
}
