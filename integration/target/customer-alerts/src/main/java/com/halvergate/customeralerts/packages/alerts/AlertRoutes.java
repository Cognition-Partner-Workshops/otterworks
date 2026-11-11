package com.halvergate.customeralerts.packages.alerts;

import java.math.BigDecimal;
import java.util.List;
import javax.sql.DataSource;
import com.halvergate.customeralerts.runtime.OutputQueueDeclarer;
import com.halvergate.customeralerts.runtime.TransactionOutcomeLogger;
import org.apache.camel.CamelContext;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.spring.boot.CamelContextConfiguration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class AlertRoutes extends RouteBuilder implements CamelContextConfiguration {
    private static final Logger LOG = LoggerFactory.getLogger(AlertRoutes.class);
    private final JdbcTemplate jdbc;
    private final AlertPublisher publisher;
    private final TransactionOutcomeLogger outcomes;
    private final OutputQueueDeclarer queues;
    static final List<Flow> FLOWS = List.of(
        new Flow("card-dispute", "HB.ALERTS.CARD.DISPUTE", "HB.DISPUTE.RECEIVED", "dispute_cases", ""),
        new Flow("large-transaction", "HB.ALERTS.LARGE.TRANSACTION", "HB.LARGE.TRANSACTION.ALERTED",
            "large_alert_dispatch", "&selector=customerType%20%3D%20%27RETAIL%27"),
        new Flow("low-balance", "HB.ALERTS.LOW.BALANCE", "HB.LOW.BALANCE.ALERTED", "alert_dispatch",
            "&selector=customerType%20%3D%20%27RETAIL%27"));

    record Flow(String name, String input, String output, String table, String selector) { }

    public AlertRoutes(@Qualifier("autoCommitDataSource") DataSource source, AlertPublisher publisher,
                       TransactionOutcomeLogger outcomes, OutputQueueDeclarer queues) {
        jdbc = new JdbcTemplate(source);
        this.publisher = publisher;
        this.outcomes = outcomes;
        this.queues = queues;
    }

    @Override
    public void configure() {
        errorHandler(new org.apache.camel.builder.SpringTransactionErrorHandlerBuilder().maximumRedeliveries(0));
        for (Flow flow : FLOWS) {
            from("jms:queue:" + flow.input() + "?transacted=true&cacheLevelName=CACHE_NONE"
                + "&exposeListenerSession=true&concurrentConsumers=1&recoveryInterval=100" + flow.selector())
                .routeId("customer-alerts." + flow.name()).autoStartup(false)
                .transacted("required")
                .process(exchange -> {
                    String id = exchange.getMessage().getHeader("requestId", String.class);
                    outcomes.register(id);
                    LOG.info("requestId={} in-tx receive", id);
                })
                .to("xslt-saxon:packages/alerts/Transforms/" + flow.name() + ".xsl")
                .process(exchange -> {
                    var record = AlertRecord.parse(exchange.getMessage().getBody(String.class));
                    exchange.setProperty("alerts.filtered", record.filtered());
                    if (!record.filtered()) {
                        insert(flow, record);
                        LOG.info("requestId={} in-tx inserted (AUTO_COMMIT)", record.id());
                        exchange.getMessage().setBody(record.body());
                    }
                })
                .filter(exchangeProperty("alerts.filtered").isEqualTo(false))
                    .process(exchange -> {
                        publisher.publish(exchange, flow.output());
                        LOG.info("requestId={} in-tx published",
                            exchange.getMessage().getHeader("requestId", String.class));
                    })
                .end();
        }
    }

    void insert(Flow flow, AlertRecord record) {
        jdbc.update("INSERT INTO " + flow.table()
            + " (flow,request_id,account_id,amount,currency,status) VALUES (?,?,?,?,?,?)",
            "customer-alerts." + flow.name(), record.id(), record.account(), new BigDecimal(record.amount()),
            record.currency(), record.status());
    }

    @Override
    public void beforeApplicationStart(CamelContext context) {
        try {
            queues.declare();
            jdbc.queryForObject("SELECT 1", Integer.class);
            for (Flow flow : FLOWS) {
                context.getEndpoint("xslt-saxon:packages/alerts/Transforms/" + flow.name() + ".xsl").start();
            }
        } catch (Exception e) {
            throw new IllegalStateException("Alerts dependencies are not ready", e);
        }
    }

    @Override
    public void afterApplicationStart(CamelContext context) {
        try {
            for (Flow flow : FLOWS) {
                context.getRouteController().startRoute("customer-alerts." + flow.name());
            }
        } catch (Exception e) {
            throw new IllegalStateException("Alerts receivers could not start", e);
        }
    }
}
