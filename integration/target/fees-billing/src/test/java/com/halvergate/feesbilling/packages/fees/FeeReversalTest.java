package com.halvergate.feesbilling.packages.fees;

import static org.assertj.core.api.Assertions.assertThat;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;
import net.minidev.json.JSONValue;
import com.halvergate.feesbilling.runtime.TransactionOutcomeLogger;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.xml.transform.dom.DOMResult;
import javax.xml.transform.stream.StreamSource;
import java.io.StringReader;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.server.embedded.EmbeddedActiveMQ;
import org.apache.activemq.artemis.core.settings.impl.AddressSettings;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.component.jms.JmsComponent;
import org.apache.camel.spring.spi.SpringTransactionPolicy;
import org.h2.jdbcx.JdbcDataSource;
import org.junit.jupiter.api.Test;
import org.springframework.jms.connection.JmsTransactionManager;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.w3c.dom.Document;

class FeeReversalTest {
    static JSONObject corpus() throws Exception {
        Path path = Path.of("../../corpus/fees-billing.fee-reversal/flow.json");
        return (JSONObject) JSONValue.parse(Files.readString(path));
    }

    static JSONObject object(JSONObject parent, String key) { return (JSONObject) parent.get(key); }
    static JSONArray array(JSONObject parent, String key) { return (JSONArray) parent.get(key); }

    @Test
    void everyFrozenTransformMatchesBodyAndDatabaseFields() throws Exception {
        var factory = new net.sf.saxon.TransformerFactoryImpl();
        var resource = getClass().getResource("/packages/fees/Transforms/fee-reversal.xsl");
        var templates = factory.newTemplates(new StreamSource(resource.toExternalForm()));
        JSONObject flow = corpus();
        var inputs = array(object(flow, "inputs"), "messages");
        var expected = object(flow, "expected");
        for (int i = 0; i < inputs.size(); i++) {
            var output = new DOMResult();
            templates.newTransformer().transform(new StreamSource(new StringReader(
                ((JSONObject) inputs.get(i)).getAsString("body"))), output);
            var result = ((Document) output.getNode()).getDocumentElement();
            var row = (JSONObject) array(object(expected, "db"), "fee_reversals").get(i);
            assertThat(result.getAttribute("id")).isEqualTo(row.getAsString("request_id"));
            assertThat(result.getAttribute("account")).isEqualTo(row.getAsString("account_id"));
            assertThat(result.getAttribute("currency")).isEqualTo(row.getAsString("currency"));
            for (String field : new String[]{"amount", "status"}) {
                assertThat(result.getElementsByTagName(field).item(0).getTextContent())
                    .isEqualTo(row.getAsString(field));
            }
            assertThat(result.getElementsByTagName("body").item(0).getTextContent()).isEqualTo(
                ((JSONObject) array(expected, "messages").get(i)).getAsString("body"));
        }
    }

    @Test
    void consumeCommitAndRollbackPreserveAutoCommitAndLiteralOutput() throws Exception {
        var broker = new EmbeddedActiveMQ();
        broker.setConfiguration(new ConfigurationImpl().setPersistenceEnabled(false)
            .setSecurityEnabled(false).addAcceptorConfiguration("invm", "vm://17")
            .addAddressSetting("#", new AddressSettings().setMaxDeliveryAttempts(4)
                .setRedeliveryDelay(10).setDeadLetterAddress(SimpleString.of("HB.UNDLV"))));
        broker.start();
        try (var factory = new ActiveMQConnectionFactory("vm://17");
             var context = new DefaultCamelContext()) {
            for (String queue : new String[]{"HB.FEE.REVERSAL", "HB.FEE.REVERSED", "HB.UNDLV"}) {
                broker.getActiveMQServer().createQueue(QueueConfiguration.of(queue).setAddress(queue)
                    .setRoutingType(RoutingType.ANYCAST).setDurable(true));
            }
            var source = new JdbcDataSource();
            source.setURL("jdbc:h2:mem:fees;DB_CLOSE_DELAY=-1");
            var jdbc = new JdbcTemplate(source);
            jdbc.execute("CREATE TABLE fee_reversals (flow VARCHAR, request_id VARCHAR PRIMARY KEY, account_id VARCHAR, amount DECIMAL(18,2), currency VARCHAR, status VARCHAR)");
            var transactions = new JmsTransactionManager(factory);
            transactions.setTransactionSynchronization(
                org.springframework.transaction.support.AbstractPlatformTransactionManager.SYNCHRONIZATION_ALWAYS);
            var policy = new SpringTransactionPolicy(transactions);
            policy.setPropagationBehaviorName("PROPAGATION_REQUIRED");
            context.getRegistry().bind("required", policy);
            var component = JmsComponent.jmsComponentTransacted(factory, transactions);
            component.setCacheLevelName("CACHE_NONE");
            component.setExposeListenerSession(true);
            context.addComponent("jms", component);
            context.addRoutes(new FeeReversalRoute(source,
                new FeeReversalPublisher("vm://17", null, null), new TransactionOutcomeLogger()));
            context.start();
            context.getRouteController().startRoute(FeeReversalRoute.ROUTE);
            var jms = new JmsTemplate(factory);
            jms.setReceiveTimeout(3000);
            JSONObject flow = corpus();
            var inputs = array(object(flow, "inputs"), "messages");
            for (int i = 0; i < inputs.size(); i++) {
                send(jms, (JSONObject) inputs.get(i));
                var output = (jakarta.jms.TextMessage) jms.receive("HB.FEE.REVERSED");
                var expected = (JSONObject) array(object(flow, "expected"), "messages").get(i);
                assertThat(output).isNotNull();
                assertThat(output.getText()).isEqualTo(expected.getAsString("body"));
                assertThat(output.getJMSDeliveryMode()).isEqualTo(jakarta.jms.DeliveryMode.PERSISTENT);
                var names = java.util.Collections.list(output.getPropertyNames());
                assertThat(names).containsExactlyInAnyOrder("requestId", "accountId", "JMSXGroupID", "sequence", "JMSXDeliveryCount");
                assertThat(output.getIntProperty("JMSXDeliveryCount")).isEqualTo(1);
                object(expected, "headers").forEach((key, value) -> {
                    var core = ((org.apache.activemq.artemis.jms.client.ActiveMQMessage) output).getCoreMessage();
                    assertThat(core.getStringProperty(key)).isEqualTo(value.toString());
                });
            }
            assertThat(jdbc.queryForObject("SELECT count(*) FROM fee_reversals", Integer.class)).isEqualTo(2);
            send(jms, (JSONObject) inputs.get(0));
            var duplicate = jms.receive("HB.UNDLV");
            assertThat(duplicate).isNotNull();
            assertThat(duplicate.getIntProperty("JMSXDeliveryCount")).isGreaterThanOrEqualTo(1);
            assertThat(jdbc.queryForObject("SELECT count(*) FROM fee_reversals", Integer.class)).isEqualTo(2);
            jms.convertAndSend("HB.FEE.REVERSAL", "");
            assertThat(jms.receive("HB.UNDLV")).isNotNull();
            jms.setReceiveTimeout(100);
            assertThat(jms.receive("HB.FEE.REVERSED")).isNull();
            assertThat(jms.receive("HB.FEE.REVERSAL")).isNull();
        } finally {
            broker.stop();
        }
    }

    static void send(JmsTemplate jms, JSONObject input) {
        jms.send("HB.FEE.REVERSAL", session -> {
            var message = session.createTextMessage(input.getAsString("body"));
            var fields = object(input, "properties").entrySet().iterator();
            while (fields.hasNext()) {
                var field = fields.next();
                message.setStringProperty(field.getKey(), field.getValue().toString());
            }
            return message;
        });
    }
}
