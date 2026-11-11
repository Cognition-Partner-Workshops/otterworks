import org.apache.activemq.artemis.api.core.client.ActiveMQClient;
import org.apache.activemq.artemis.api.core.client.ClientRequestor;
import org.apache.activemq.artemis.api.core.client.ClientSession;
import org.apache.activemq.artemis.api.core.management.ManagementHelper;
import org.apache.activemq.artemis.api.core.SimpleString;

public class ArtemisSnapshot {
    private static String request(ClientSession session, String resource, String name, boolean attribute,
                                  Object... parameters) throws Exception {
        try (var requestor = new ClientRequestor(session, "activemq.management")) {
            var message = session.createMessage(false);
            if (attribute) {
                ManagementHelper.putAttribute(message, resource, name);
            } else {
                ManagementHelper.putOperationInvocation(message, resource, name, parameters);
            }
            var reply = requestor.request(message, 5000);
            if (reply == null || (!attribute && !ManagementHelper.hasOperationSucceeded(reply))) {
                throw new IllegalStateException("Management failed: " + resource + "." + name);
            }
            var json = reply.getReadOnlyBodyBuffer().readNullableSimpleString().toString();
            return json.substring(1, json.length() - 1);
        }
    }

    public static void main(String[] args) throws Exception {
        try (var locator = ActiveMQClient.createServerLocator("tcp://localhost:61616");
             var factory = locator.createSessionFactory();
             var session = factory.createSession(System.getenv("ARTEMIS_USER"), System.getenv("ARTEMIS_PASSWORD"),
                 false, true, true, false, 0)) {
            session.start();
            var result = new StringBuilder("{\"prepared\":")
                .append(request(session, "broker", "listPreparedTransactions", false)).append(",\"queues\":{");
            var names = new String[]{"HB.PAYMENT.INSTRUCTIONS", "HB.PAYMENT.STATUS", "HB.UNDLV"};
            for (int i = 0; i < names.length; i++) {
                if (i > 0) { result.append(','); }
                var resource = "queue." + names[i];
                result.append('"').append(names[i]).append("\":{\"messageCount\":")
                    .append(request(session, resource, "messageCount", true)).append(",\"deliveringCount\":")
                    .append(request(session, resource, "deliveringCount", true)).append('}');
            }
            var queue = session.queueQuery(SimpleString.of("HB.PAYMENT.STATUS"));
            result.append("},\"statusQueue\":{\"durable\":").append(queue.isDurable())
                .append(",\"autoDelete\":").append(queue.isAutoDelete())
                .append(",\"routingType\":\"").append(queue.getRoutingType()).append("\"},\"statusMessages\":")
                .append(request(session, "queue.HB.PAYMENT.STATUS", "listMessages", false, "")).append('}');
            System.out.println("SNAPSHOT " + result);
        }
    }
}
