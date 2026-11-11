package com.halvergate.feesbilling.packages.fees;

import com.halvergate.feesbilling.runtime.TransactionOutcomeLogger;
import java.math.BigDecimal;
import javax.sql.DataSource;
import org.apache.camel.CamelContext;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.spring.boot.CamelContextConfiguration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.w3c.dom.Document;

@Component
public class FeeReversalRoute extends RouteBuilder {
    static final String ROUTE = "fees-billing.fee-reversal";
    static final String TRANSFORM = "xslt-saxon:packages/fees/Transforms/fee-reversal.xsl?output=DOM";
    private static final Logger LOG = LoggerFactory.getLogger(FeeReversalRoute.class);
    private final JdbcTemplate jdbc;
    private final FeeReversalPublisher publisher;
    private final TransactionOutcomeLogger outcomes;

    public FeeReversalRoute(@Qualifier("autoCommitDataSource") DataSource source,
            FeeReversalPublisher publisher, TransactionOutcomeLogger outcomes) {
        this.jdbc = new JdbcTemplate(source);
        this.publisher = publisher;
        this.outcomes = outcomes;
    }

    @Override
    public void configure() {
        from("jms:queue:HB.FEE.REVERSAL?transacted=true")
            .routeId(ROUTE).autoStartup(false).transacted("required")
            .process(exchange -> {
                String id = exchange.getMessage().getHeader("requestId", String.class);
                outcomes.register(id);
                LOG.info("requestId={} in-tx receive", id);
            })
            .to(TRANSFORM)
            .process(exchange -> {
                var result = exchange.getMessage().getBody(Document.class).getDocumentElement();
                String id = result.getAttribute("id");
                String amount = result.getElementsByTagName("amount").item(0).getTextContent();
                String status = result.getElementsByTagName("status").item(0).getTextContent();
                jdbc.update("INSERT INTO fee_reversals (flow,request_id,account_id,amount,currency,status) VALUES (?,?,?,?,?,?)",
                    ROUTE, id, result.getAttribute("account"), new BigDecimal(amount),
                    result.getAttribute("currency"), status);
                LOG.info("requestId={} in-tx inserted", id);
                exchange.getMessage().setBody(result.getElementsByTagName("body").item(0).getTextContent());
            })
            .process(publisher::publish)
            .process(exchange -> LOG.info("requestId={} in-tx published",
                exchange.getMessage().getHeader("requestId")));
    }

    @Bean
    CamelContextConfiguration feesReadiness() {
        return new CamelContextConfiguration() {
            @Override
            public void beforeApplicationStart(CamelContext context) {
                jdbc.queryForObject("SELECT count(*) FROM fee_reversals", Long.class);
                context.getEndpoint(TRANSFORM);
            }

            @Override
            public void afterApplicationStart(CamelContext context) {
                try {
                    context.getRouteController().startRoute(ROUTE);
                } catch (Exception e) {
                    throw new IllegalStateException("Fee reversal is not ready", e);
                }
            }
        };
    }
}
