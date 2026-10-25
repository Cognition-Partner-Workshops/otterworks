package example.claimshub.fnol;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.camel.AggregationStrategy;
import org.apache.camel.Exchange;
import org.apache.camel.builder.PredicateBuilder;
import org.apache.camel.builder.RouteBuilder;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * The FnolIntake orchestration as Camel routes. Shape names in the comments are the XLANG/s ones.
 *
 * <ul>
 * <li>{@code fnol.receive}: Receive_Fnol and Listen_Correction. The ClaimNumberCorrelation becomes an
 * aggregator on the promoted claim number; the correlated receive is completion on the second message (the
 * correction replaces the first), the Delay is the completion timeout.</li>
 * <li>{@code fnol.intake}: the instance, from Construct_Canonical to Decide_Assignment.</li>
 * <li>{@code messagebox.triage-facts}, {@code messagebox.insert-claim}: the content-based send ports
 * sp_Fraud_Referral_FILE, sp_Declines_FILE and sp_GlassVendor_FastTrack_SFTP.</li>
 * </ul>
 * The port and subscription routes have no error handler of their own, so a failure there suspends the instance in
 * {@code fnol.intake}.
 */
@Component
@EnableConfigurationProperties(FnolIntakeProperties.class)
public class FnolIntakeRoute extends RouteBuilder {

    public static final String FNOL_IN = "direct:fnol.in";

    static final String DECLINE = "DECLINE_NOT_IN_FORCE";
    static final String FRAUD = "FRAUD_REVIEW";
    static final String FAST_TRACK = "FAST_TRACK";

    private static final String FNOL = "/*[local-name()='ClaimsSvcRq']/*[local-name()='ClaimsNotificationAddRq']";
    private static final String AGGREGATE_NS = "http://schemas.microsoft.com/BizTalk/2003/aggschema";
    private static final Pattern TRIAGE_OUTCOME = Pattern.compile("<TriageOutcome\\b[^>]*?(/>|>[^<]*</TriageOutcome>)");

    private final FnolIntakeProperties properties;
    private final ClaimTriage triage;

    public FnolIntakeRoute(FnolIntakeProperties properties, ClaimTriage triage) {
        this.properties = properties;
        this.triage = triage;
    }

    @Override
    public void configure() {
        if (!Files.isDirectory(properties.mapsDir())) {
            // The image carries no fixture; FnolIntake waits for the converted maps instead of failing the context.
            log.warn("FnolIntake routes not started: no BizTalk maps at {} (set claimshub.fnol.fixture-dir)", properties.mapsDir());
            return;
        }
        // Receive_Fnol (activating, initializes ClaimNumberCorrelation), with the FNOL schema's promotions.
        from(FNOL_IN).routeId("fnol.receive")
                .convertBodyTo(String.class)
                .setHeader("ClaimNumber").xpath(FNOL + "/*[local-name()='ClaimsOccurrence']/*[local-name()='ClaimNumber']", String.class)
                .setHeader("LossCauseCd").xpath(FNOL + "/*[local-name()='ClaimsOccurrence']/*[local-name()='LossCauseCd']", String.class)
                .setHeader("AgencyId").xpath(FNOL + "/*[local-name()='Producer']/*[local-name()='ProducerId']", String.class)
                // Listen_Correction: Receive_Correction (follows the correlation) or Delay_CorrectionWindow.
                .aggregate(header("ClaimNumber"), correctionReplacesFirst())
                    .completionSize(2)
                    .completionTimeout(properties.correctionWindow().toMillis())
                    .completionTimeoutCheckerInterval(250)
                    .parallelProcessing()
                .to("direct:fnol.instance");

        from("direct:fnol.instance").routeId("fnol.intake")
                .onException(Exception.class).handled(true)
                    .setHeader("FnolStatus", constant("SUSPENDED"))
                    .setHeader("FnolSuspendedReason", simple("${exception.message}"))
                    .to(properties.suspendedUri())
                .end()
                // Construct_Canonical / Construct_Canonical_From_Correction
                .to(map("Fnol_to_CanonicalClaim.xslt"))
                .setProperty("msgClaim", body())
                // Construct_PolicyRq
                .to(map("CanonicalClaim_to_PolicyInqRq.xslt"))
                .setProperty("msgPolicyRq", body())
                // Send_PolicyRq / Receive_PolicyRs: WCF-SQL usp_GetPolicyAsOf
                .to("direct:port.policy-lookup")
                .setProperty("msgPolicyRs", body())
                // Construct_InsertClaim: the two-source map reads BizTalk's multi-part aggregate
                .process(this::aggregateClaimAndPolicy)
                .to(map("Claim_PolicyInqRs_to_InsertClaim.xslt"))
                .setProperty("msgInsertClaim", body())
                // Construct_TriageFacts: the scripting-functoid map runs as its .golden.xslt twin
                .to(map("InsertClaim_to_TriageFacts.golden.xslt"))
                .setProperty("msgTriageFacts", body())
                // Call_Rules ClaimTriage, then Expression_ReadOutcome
                .process(this::callRules)
                .setHeader("TriageOutcome", exchangeProperty("triageOutcome"))
                // The facts, with the outcome promoted, are what sp_Fraud_Referral_FILE and sp_Declines_FILE subscribe to.
                .setBody(exchangeProperty("msgTriageFactsRuled"))
                .to("direct:messagebox.triage-facts")
                // Decide_Outcome
                .choice()
                    .when(exchangeProperty("triageOutcome").isEqualTo(DECLINE))
                        .setHeader("FnolStatus", constant("TERMINATED"))
                        .setHeader("FnolTerminateReason", simple("FNOL ${header.ClaimNumber} declined: policy not in force at loss date"))
                        .to(properties.completedUri())
                        .stop()
                .end()
                // Construct_InsertClaim_WithOutcome, Send_InsertClaim
                .process(this::assignOutcome)
                .to("direct:port.insert-claim")
                .setBody(exchangeProperty("msgInsertClaimWithOutcome"))
                .to("direct:messagebox.insert-claim")
                // Decide_Assignment: fast tracks are settled from the desk
                .choice()
                    .when(exchangeProperty("triageOutcome").isNotEqualTo(FAST_TRACK))
                        .setBody(exchangeProperty("msgInsertClaimWithOutcome"))
                        .to(properties.assignmentUri())
                .end()
                .setHeader("FnolStatus", constant("COMPLETED"))
                .to(properties.completedUri());

        // sp_PolicyAdmin_PolicyInq_WcfSql, solicit-response
        from("direct:port.policy-lookup").routeId("port.policy-lookup")
                .errorHandler(noErrorHandler())
                .setHeader("msgPolicyRq", body())
                .to("sql:select cast(usp_get_policy_as_of(xmlparse(document :#msgPolicyRq)) as text) as rs?outputType=SelectOne")
                .removeHeader("msgPolicyRq")
                .filter(body().isNull())
                    .throwException(IllegalStateException.class, "usp_GetPolicyAsOf found no policy version as of the loss date")
                .end();

        // sp_ClaimsDb_InsertClaim_WcfSql, one-way; the claims system's key refuses a second claim with the same number
        from("direct:port.insert-claim").routeId("port.insert-claim")
                .errorHandler(noErrorHandler())
                .setHeader("msgInsertClaim", exchangeProperty("msgInsertClaimWithOutcome"))
                .to("sql:select usp_insert_claim(xmlparse(document :#msgInsertClaim))?outputType=SelectOne")
                .removeHeader("msgInsertClaim");

        Path out = properties.outPath();

        // Subscriptions on TriageFacts: sp_Fraud_Referral_FILE, sp_Declines_FILE
        from("direct:messagebox.triage-facts").routeId("messagebox.triage-facts")
                .errorHandler(noErrorHandler())
                .choice()
                    .when(header("TriageOutcome").isEqualTo(FRAUD))
                        .to(file(out.resolve("fraud-desk/referrals"), "${header.ClaimNumber}.xml"))
                    .when(header("TriageOutcome").isEqualTo(DECLINE))
                        .to(file(out.resolve("agency-liaison/declines"), "${header.AgencyId}/${header.ClaimNumber}.xml"))
                .end();

        // Subscription on usp_InsertClaim: sp_GlassVendor_FastTrack_SFTP (a file drop until the SFTP endpoint is configured)
        from("direct:messagebox.insert-claim").routeId("messagebox.insert-claim")
                .errorHandler(noErrorHandler())
                .filter(PredicateBuilder.and(header("TriageOutcome").isEqualTo(FAST_TRACK), header("LossCauseCd").isEqualTo("GLAS")))
                    .to(file(out.resolve("glassnet/thistlecombe/fasttrack"), "${header.ClaimNumber}.xml"));
    }

    private String map(String xslt) {
        return "xslt-saxon:" + properties.mapsDir().resolve(xslt).toUri();
    }

    private static String file(Path dir, String fileName) {
        return "file:" + dir + "?fileName=" + fileName;
    }

    /** A second FNOL inside the window replaces the first one (msgFnolCorrection wins). */
    static AggregationStrategy correctionReplacesFirst() {
        return (oldExchange, newExchange) -> newExchange;
    }

    private void aggregateClaimAndPolicy(Exchange exchange) {
        String claim = exchange.getProperty("msgClaim", String.class);
        String policy = exchange.getProperty("msgPolicyRs", String.class);
        exchange.getMessage().setBody("<ns0:Root xmlns:ns0=\"" + AGGREGATE_NS + "\"><InputMessagePart_0>" + claim
                + "</InputMessagePart_0><InputMessagePart_1>" + policy + "</InputMessagePart_1></ns0:Root>");
    }

    private void callRules(Exchange exchange) {
        String facts = exchange.getProperty("msgTriageFacts", String.class);
        TriageResult result = triage.evaluate(exchange.getMessage().getHeader("ClaimNumber", String.class), facts);
        StringBuilder written = new StringBuilder("<Outcome>").append(escape(result.outcome())).append("</Outcome>");
        result.reasons().forEach(r -> written.append("<Reason>").append(escape(r)).append("</Reason>"));
        int close = facts.lastIndexOf("</");
        exchange.setProperty("msgTriageFactsRuled", facts.substring(0, close) + written + facts.substring(close));
        exchange.setProperty("triageOutcome", result.outcome());
    }

    /** The message assignment writes the outcome into the nil TriageOutcome element and promotes it. */
    private void assignOutcome(Exchange exchange) {
        String insert = exchange.getProperty("msgInsertClaim", String.class);
        Matcher m = TRIAGE_OUTCOME.matcher(insert);
        if (!m.find()) {
            throw new IllegalStateException("usp_InsertClaim has no TriageOutcome element");
        }
        String outcome = exchange.getProperty("triageOutcome", String.class);
        exchange.setProperty("msgInsertClaimWithOutcome",
                insert.substring(0, m.start()) + "<TriageOutcome>" + escape(outcome) + "</TriageOutcome>" + insert.substring(m.end()));
    }

    private static String escape(String text) {
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
