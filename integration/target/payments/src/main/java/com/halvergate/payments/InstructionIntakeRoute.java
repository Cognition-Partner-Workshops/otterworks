package com.halvergate.payments;

import java.io.StringReader;
import java.math.BigDecimal;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;

import org.apache.camel.Exchange;
import org.apache.camel.spring.SpringRouteBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.w3c.dom.Element;
import org.w3c.dom.Document;
import org.xml.sax.InputSource;

@Component
public class InstructionIntakeRoute extends SpringRouteBuilder {
    private static final Logger LOG = LoggerFactory.getLogger(InstructionIntakeRoute.class);
    private final JdbcTemplate jdbc;
    private final long holdMillis;
    private final XaStatusPublisher publisher;
    private final AtomicBoolean firstTransaction = new AtomicBoolean(true);

    public InstructionIntakeRoute(JdbcTemplate jdbc, XaStatusPublisher publisher,
                                  @Value("${payments.tx-hold-ms:0}") long holdMillis) {
        this.jdbc = jdbc;
        this.publisher = publisher;
        this.holdMillis = holdMillis;
    }

    @Override
    public void configure() {
        errorHandler(transactionErrorHandler().maximumRedeliveries(0));
        from("jms:queue:HB.PAYMENT.INSTRUCTIONS?transacted=true&cacheLevelName=CACHE_NONE&concurrentConsumers=1&exposeListenerSession=true&recoveryInterval=100&consumerType=Custom&messageListenerContainerFactory=#paymentsListener")
            .routeId("payments.instruction-intake")
            .autoStartup(false)
            .transacted("required")
            .process(this::observeTransaction)
            .to("xslt-saxon:Transforms/payment-status.xsl?output=DOM")
            .process(this::post)
            .removeHeaders("*", "requestId", "accountId", "JMSXGroupID", "sequence")
            .process(publisher::publish)
            .process(exchange -> LOG.info("in-tx published requestId={}", exchange.getProperty("requestId")))
            .process(exchange -> {
                if (holdMillis > 0 && Boolean.TRUE.equals(exchange.getProperty("holdTransaction"))) {
                    LOG.info("in-tx hold requestId={} redelivered={} deliveryCount={} holdMs={}",
                        exchange.getProperty("requestId"), exchange.getProperty("redelivered"),
                        exchange.getProperty("deliveryCount"), holdMillis);
                    Thread.sleep(holdMillis);
                }
            });
    }

    private void observeTransaction(Exchange exchange) {
        String id = exchange.getMessage().getHeader("requestId", String.class);
        exchange.setProperty("requestId", id);
        exchange.setProperty("holdTransaction", firstTransaction.getAndSet(false));
        exchange.setProperty("redelivered", exchange.getMessage().getHeader("JMSRedelivered"));
        exchange.setProperty("deliveryCount", exchange.getMessage().getHeader("JMSXDeliveryCount"));
        LOG.info("in-tx receive requestId={} redelivered={} deliveryCount={}", id,
            exchange.getProperty("redelivered"), exchange.getProperty("deliveryCount"));
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCompletion(int status) {
                LOG.info("tx outcome requestId={} outcome={}", id,
                    status == STATUS_COMMITTED ? "COMMIT" : status == STATUS_ROLLED_BACK ? "ROLLBACK" : "UNKNOWN");
            }
        });
    }

    private void post(Exchange exchange) throws Exception {
        Element result = exchange.getMessage().getBody(Document.class).getDocumentElement();
        Object[] values = {"payments.instruction-intake", result.getAttribute("id"), result.getAttribute("account"),
            new BigDecimal(text(result, "amount")), result.getAttribute("currency"), text(result, "status")};
        jdbc.update("INSERT INTO payment_inbox (flow,request_id,account_id,amount,currency,status) VALUES (?,?,?,?,?,?)", values);
        LOG.info("in-tx inbox inserted requestId={}", exchange.getProperty("requestId"));
        jdbc.update("INSERT INTO payment_ledger (flow,request_id,account_id,amount,currency,status) VALUES (?,?,?,?,?,?)", values);
        LOG.info("in-tx ledger inserted requestId={}", exchange.getProperty("requestId"));
        exchange.getMessage().setBody(text(result, "body"));
    }

    static Element result(String xml) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
        return factory.newDocumentBuilder().parse(new InputSource(new StringReader(xml))).getDocumentElement();
    }

    static String text(Element result, String name) {
        return result.getElementsByTagName(name).item(0).getTextContent();
    }
}
