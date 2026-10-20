package example.claimshub.orchestrations;

import java.nio.charset.StandardCharsets;

import org.apache.camel.AggregationStrategy;
import org.apache.camel.Exchange;

/**
 * Joins the two branches of the parallel shape. The roster branch carries the RosterResult; the archive branch
 * only has to have finished. The result is the two-part message BizTalk hands a multi-source map:
 * {@code InputMessagePart_0} the roster, {@code InputMessagePart_1} the request.
 */
public class AssignmentAggregationStrategy implements AggregationStrategy {

    static final String AGGSCHEMA = "http://schemas.microsoft.com/BizTalk/2003/aggschema";

    @Override
    public Exchange aggregate(Exchange oldExchange, Exchange newExchange) {
        Exchange result = oldExchange == null ? newExchange : oldExchange;
        if (newExchange.getException() != null) {
            result.setException(newExchange.getException());
        }
        if (AdjusterAssignmentRoute.ROSTER_BRANCH.equals(newExchange.getProperty(AdjusterAssignmentRoute.BRANCH, String.class))) {
            String roster = newExchange.getMessage().getBody(String.class);
            String request = withoutDeclaration(new String(
                    newExchange.getProperty(AdjusterAssignmentRoute.REQUEST, byte[].class), StandardCharsets.UTF_8));
            result.getMessage().setBody("<ns0:Root xmlns:ns0=\"" + AGGSCHEMA + "\"><InputMessagePart_0>" + roster
                    + "</InputMessagePart_0><InputMessagePart_1>" + request + "</InputMessagePart_1></ns0:Root>");
            result.setProperty(AdjusterAssignmentRoute.ROSTER_RECEIVED, true);
        }
        return result;
    }

    static String withoutDeclaration(String xml) {
        String s = xml.startsWith("\uFEFF") ? xml.substring(1) : xml;
        return s.startsWith("<?xml") ? s.substring(s.indexOf("?>") + 2) : s;
    }
}
