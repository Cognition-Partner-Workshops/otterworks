package example.claimshub.inbox;

import org.apache.camel.Exchange;
import org.apache.camel.builder.RouteBuilder;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import example.claimshub.OrchestrationEndpoints;
import example.claimshub.fnol.FnolIntakeRoute;

/**
 * Local file drops for the two receive locations that are not FILE in the binding, so the corpus can be replayed
 * against a running hub: rp_Agency_FnolBatch_SFTP (one FNOL per file, no batch disassembly) and
 * rp_ClaimsSystem_AssignmentRequest_WcfSql (one request per file instead of typed polling). Also a tracking
 * sink, standing in for BizTalk message tracking, for the FnolIntake completed and suspended reports. Off unless
 * {@code claimshub.local-inbox.enabled=true}.
 */
@Component
@ConditionalOnProperty(name = "claimshub.local-inbox.enabled", havingValue = "true")
public class LocalInboxRoutes extends RouteBuilder {

    public static final String FNOL_TRACKING = "direct:tracking.fnol";

    @Override
    public void configure() {
        from("file:{{claimshub.local-inbox.dir}}/fnol?include=.*\\.xml&move=.done&moveFailed=.error")
                .routeId("inbox.fnol")
                .convertBodyTo(String.class)
                .to(FnolIntakeRoute.FNOL_IN);
        from("file:{{claimshub.local-inbox.dir}}/assignment?include=.*\\.xml&move=.done&moveFailed=.error")
                .routeId("inbox.assignment")
                .to(OrchestrationEndpoints.of("AdjusterAssignment"));
        // claimshub.fnol.completed-uri / suspended-uri = direct:tracking.fnol
        from(FNOL_TRACKING).routeId("tracking.fnol")
                .process(LocalInboxRoutes::instanceRecord)
                .to("file:{{claimshub.local-inbox.dir}}/tracking/fnol?fileName=${header.ClaimNumber}.xml");
    }

    static void instanceRecord(Exchange e) {
        var m = e.getMessage();
        String facts = e.getProperty("msgTriageFactsRuled", String.class);
        String insert = firstNonNull(e.getProperty("msgInsertClaimWithOutcome", String.class), e.getProperty("msgInsertClaim", String.class));
        m.setBody("<FnolInstance>"
                + element("ClaimNumber", m.getHeader("ClaimNumber", String.class))
                + element("FnolStatus", m.getHeader("FnolStatus", String.class))
                + element("TriageOutcome", m.getHeader("TriageOutcome", String.class))
                + element("Reason", firstNonNull(m.getHeader("FnolTerminateReason", String.class), m.getHeader("FnolSuspendedReason", String.class)))
                + "<TriageFactsRuled>" + embedded(facts) + "</TriageFactsRuled>"
                + "<InsertClaim>" + embedded(insert) + "</InsertClaim>"
                + "</FnolInstance>");
    }

    private static String embedded(String xml) {
        return xml == null ? "" : xml.replaceFirst("^<\\?xml[^>]*\\?>", "");
    }

    private static String firstNonNull(String a, String b) {
        return a != null ? a : b;
    }

    private static String element(String name, String value) {
        if (value == null) {
            return "<" + name + "/>";
        }
        return "<" + name + ">" + value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</" + name + ">";
    }
}
