package com.halvergate.payments.packages.returns;

import java.math.BigDecimal;
import org.apache.camel.Exchange;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.support.SynchronizationAdapter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

/**
 * halvergate.payments.payment-returns: JMS receive, receipt projection, AUTO_COMMIT insert, publish.
 * Only the inbound acknowledgement is transacted (local JMS session); the insert commits on its own
 * and a failure after it surfaces as a duplicate key on redelivery, exactly as the BW process does.
 */
@Component
public class PaymentReturnsRoute extends RouteBuilder {
    private static final Logger LOG = LoggerFactory.getLogger(PaymentReturnsRoute.class);
    private final ReturnsLedger ledger;
    private final ReturnsPublisher publisher;

    public PaymentReturnsRoute(ReturnsLedger ledger, ReturnsPublisher publisher) {
        this.ledger = ledger;
        this.publisher = publisher;
    }

    @Override
    public void configure() {
        errorHandler(defaultErrorHandler().maximumRedeliveries(0));
        from("returnsJms:queue:{{payments.returns.input-queue}}?transacted=true&lazyCreateTransactionManager=true&cacheLevelName=CACHE_NONE&concurrentConsumers=1"
                + "&exposeListenerSession=true&recoveryInterval=100")
            .routeId(ReturnsConfiguration.ROUTE_ID)
            .autoStartup(false)
            .process(this::observe)
            .to("xslt-saxon:{{payments.returns.stylesheet}}?output=DOM")
            .process(this::insert)
            .removeHeaders("*", ReturnsPublisher.CONTRACT_PROPERTIES)
            .process(publisher::publish)
            .process(exchange -> LOG.info("published requestId={} destination={}",
                exchange.getProperty("requestId"), publisher.destination()));
    }

    private void observe(Exchange exchange) {
        String id = exchange.getMessage().getHeader("requestId", String.class);
        exchange.setProperty("requestId", id);
        LOG.info("receive requestId={} redelivered={} deliveryCount={}", id,
            exchange.getMessage().getHeader("JMSRedelivered"), exchange.getMessage().getHeader("JMSXDeliveryCount"));
        exchange.getExchangeExtension().addOnCompletion(new SynchronizationAdapter() {
            @Override
            public void onComplete(Exchange done) {
                LOG.info("receive ack outcome requestId={} outcome=COMMIT", id);
            }

            @Override
            public void onFailure(Exchange done) {
                LOG.info("receive ack outcome requestId={} outcome=ROLLBACK cause={}", id,
                    done.getException() == null ? null : done.getException().getClass().getSimpleName());
            }
        });
    }

    private void insert(Exchange exchange) {
        Element result = exchange.getMessage().getBody(Document.class).getDocumentElement();
        ledger.insert(ReturnsConfiguration.ROUTE_ID, result.getAttribute("id"), result.getAttribute("account"),
            new BigDecimal(text(result, "amount")), result.getAttribute("currency"), text(result, "status"));
        LOG.info("auto-commit inserted requestId={} currency={}", exchange.getProperty("requestId"),
            result.getAttribute("currency"));
        exchange.getMessage().setBody(text(result, "body"));
    }

    static String text(Element result, String name) {
        return result.getElementsByTagName(name).item(0).getTextContent();
    }
}
