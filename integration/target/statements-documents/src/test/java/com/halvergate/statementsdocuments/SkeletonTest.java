package com.halvergate.statementsdocuments;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import java.sql.SQLException;
import java.util.List;
import javax.sql.DataSource;
import com.halvergate.statementsdocuments.runtime.IsolatedRuntimeTestConfiguration;
import dev.snowdrop.boot.narayana.core.jdbc.NarayanaDataSource;
import org.apache.camel.CamelContext;
import org.apache.camel.Route;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.builder.RouteConfigurationBuilder;
import org.apache.camel.component.jms.JmsComponent;
import org.apache.camel.model.RouteDefinition;
import org.apache.camel.model.errorhandler.SpringTransactionErrorHandlerDefinition;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Import;
import org.springframework.transaction.jta.JtaTransactionManager;
import org.springframework.util.ClassUtils;

@SpringBootTest(properties = {"spring.datasource.password=unused",
    "narayana.log-dir=target/transaction-logs", "camel.springboot.main-run-controller=false"})
@Import(IsolatedRuntimeTestConfiguration.class)
class SkeletonTest {
    @Autowired
    private ConfigurableApplicationContext applicationContext;

    @Autowired
    private CamelContext camelContext;

    @Autowired
    @Qualifier("dataSource")
    private DataSource dataSource;

    @Autowired
    @Qualifier("autoCommitDataSource")
    private DataSource autoCommitDataSource;

    @Autowired
    private JtaTransactionManager transactionManager;

    @Autowired
    @Qualifier("brokerRedelivery")
    private RouteConfigurationBuilder brokerRedelivery;

    @Test
    void startsWithPackageOwnedRoutesAndSharedRuntime() {
        assertThat(applicationContext.isActive()).isTrue();
        assertThat(camelContext.isStarted()).isTrue();
        assertThat(dataSource).isInstanceOf(NarayanaDataSource.class);
        assertThat(autoCommitDataSource).isNotSameAs(dataSource);
        var jms = camelContext.getComponent("jms", JmsComponent.class).getConfiguration();
        assertThat(jms.isTransacted()).isTrue();
        assertThat(jms.getTransactionManager()).isSameAs(transactionManager);
        assertThat(jms.getCacheLevelName()).isEqualTo("CACHE_NONE");
        assertThat(jms.isExposeListenerSession()).isTrue();
        assertThat(jms.getRecoveryInterval()).isEqualTo(100);
        assertThat(jms.isDeliveryPersistent()).isTrue();
        var configurations = brokerRedelivery.getRouteConfigurationCollection().getRouteConfigurations();
        assertThat(configurations).hasSize(1);
        var errorHandler = configurations.getFirst().getErrorHandler().getErrorHandlerType();
        assertThat(errorHandler).isInstanceOf(SpringTransactionErrorHandlerDefinition.class);
        assertThat(((SpringTransactionErrorHandlerDefinition) errorHandler)
            .getRedeliveryPolicy().getMaximumRedeliveries()).isEqualTo("0");

        String packagePrefix = "com.halvergate.statementsdocuments.packages.";
        List<RouteBuilder> packages = applicationContext.getBeansOfType(RouteBuilder.class).values().stream()
            .filter(builder -> ClassUtils.getUserClass(builder).getName().startsWith(packagePrefix)).toList();
        boolean installed = java.util.Arrays.stream(applicationContext.getBeanDefinitionNames())
            .map(applicationContext::getType).filter(java.util.Objects::nonNull)
            .anyMatch(type -> ClassUtils.getUserClass(type).getName().startsWith(packagePrefix));
        if (installed) {
            assertThat(packages).as("installed packages provide RouteBuilder beans").isNotEmpty();
        }
        for (RouteBuilder builder : packages) {
            assertThat(builder.getRouteCollection().getRoutes())
                .as("routes provided by %s", ClassUtils.getUserClass(builder).getName()).isNotEmpty();
        }
        var expected = packages.stream().flatMap(builder -> builder.getRouteCollection().getRoutes().stream())
            .map(RouteDefinition::getId).toList();
        assertThat(camelContext.getRoutes()).extracting(Route::getId)
            .containsExactlyInAnyOrderElementsOf(expected);
    }

    @Test
    void dataSourcesHaveIndependentSchemas() throws Exception {
        try (var xa = dataSource.getConnection(); var autoCommit = autoCommitDataSource.getConnection()) {
            assertThat(xa.getMetaData().getURL()).startsWith("jdbc:h2:mem:")
                .isNotEqualTo(autoCommit.getMetaData().getURL());
            assertThat(autoCommit.getAutoCommit()).isTrue();
            try (var statement = xa.createStatement()) {
                statement.execute("CREATE TABLE scaffold_isolation (id integer)");
            }
            try (var statement = autoCommit.createStatement()) {
                assertThatThrownBy(() -> statement.executeQuery("SELECT * FROM scaffold_isolation"))
                    .isInstanceOf(SQLException.class);
            }
        }
    }
}
