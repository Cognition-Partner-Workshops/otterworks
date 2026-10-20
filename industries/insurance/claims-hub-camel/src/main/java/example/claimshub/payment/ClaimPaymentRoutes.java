package example.claimshub.payment;

import example.claimshub.MapEndpoints;
import example.claimshub.maps.PaymentMapRoutes;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import org.apache.camel.Exchange;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.dataformat.bindy.fixed.BindyFixedLengthDataFormat;
import org.apache.camel.model.SagaPropagation;
import org.apache.camel.saga.InMemorySagaService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * ClaimPayment.odx as Camel routes.
 *
 * <ul>
 *   <li>{@code direct:claimPayment} is the activating receive; its doCatch is the exception handler of PaymentTx.</li>
 *   <li>The long-running scope PaymentTx is a saga. LedgerTx's compensation block, which sends the same
 *       msgLedgerPost to Ledger.ReversePayment, is the saga's compensation endpoint.</li>
 *   <li>{@code direct:vendor.deliver} is Loop_Deliver plus the send port: trailer guard, then up to three
 *       attempts inside the service window with the retry delay after each failure.</li>
 * </ul>
 */
@Component
public class ClaimPaymentRoutes extends RouteBuilder {

    public static final String CLAIM_PAYMENT = "direct:claimPayment";
    public static final String VENDOR_DELIVER = "direct:vendor.deliver";
    static final String PAYMENT_TX = "direct:claimPayment.paymentTx";
    static final String LEDGER_POST = "direct:ledger.postPayment";
    static final String LEDGER_REVERSE = "direct:ledger.reversePayment";
    static final String OPS_NOTIFY = "direct:ops.paymentHeld";

    static final String INSTRUCTION = "claimsInstruction";
    static final String SOURCE_FILE = "claimsSourceFileName";
    static final String LEDGER_DOCUMENT = "claimsLedgerPost";
    static final String ATTEMPTS = "claimsDeliveryAttempts";
    static final String DELIVERED = "claimsDelivered";
    static final String LAST_FAILURE = "claimsLastDeliveryFailure";
    /** Saga option: carries msgLedgerPost to the compensation, as the XLANG/s scope kept it. */
    static final String LEDGER_DOCUMENT_OPTION = "ClaimsLedgerPost";

    private static final DateTimeFormatter BTS2000 = DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSS");

    private final int attempts;
    private final Duration retryDelay;

    public ClaimPaymentRoutes(@Value("${claims.payment.vendor.attempts}") int attempts,
            @Value("${claims.payment.vendor.retry-delay}") Duration retryDelay) {
        this.attempts = attempts;
        this.retryDelay = retryDelay;
    }

    @Override
    public void configure() throws Exception {
        if (getCamelContext().hasService(InMemorySagaService.class) == null) {
            getCamelContext().addService(new InMemorySagaService());
        }

        from("file:{{claims.payment.inbox.directory}}?include=PI-.*\\.xml&move=.done&moveFailed=.error")
                .routeId("ClaimPayment.Inbox").autoStartup("{{claims.payment.inbox.enabled}}")
                .setHeader(Exchange.FILE_NAME, header(Exchange.FILE_NAME_ONLY))
                .to(CLAIM_PAYMENT);

        from(CLAIM_PAYMENT).routeId("ClaimPayment")
                .convertBodyTo(String.class, StandardCharsets.UTF_8.name())
                .setProperty(INSTRUCTION, body())
                .setProperty(SOURCE_FILE, header(Exchange.FILE_NAME))
                .to(MapEndpoints.of(PaymentMapRoutes.LEDGER_POST))
                .convertBodyTo(String.class)
                .setProperty(LEDGER_DOCUMENT, body())
                .doTry()
                    .to(PAYMENT_TX)
                .doCatch(VendorUnreachableException.class)
                    .to(OPS_NOTIFY)
                .end();

        from(PAYMENT_TX).routeId("ClaimPayment.PaymentTx")
                .saga().propagation(SagaPropagation.REQUIRES_NEW)
                    .option(LEDGER_DOCUMENT_OPTION, exchangeProperty(LEDGER_DOCUMENT))
                    .compensation(LEDGER_REVERSE)
                .setBody(exchangeProperty(LEDGER_DOCUMENT))
                .to(LEDGER_POST)
                .setBody(exchangeProperty(INSTRUCTION))
                .to(MapEndpoints.of(PaymentMapRoutes.VENDOR_REMITTANCE))
                .convertBodyTo(String.class)
                .process(e -> e.getMessage().setBody(RemittanceRecords.toRecords(e)))
                .setProperty(Exchange.CHARSET_NAME, constant(StandardCharsets.US_ASCII.name()))
                .marshal(new BindyFixedLengthDataFormat(RemittancePayment.class))
                .removeHeaders("CamelBindyFixedLength*")
                .setHeader(Exchange.FILE_NAME, exchangeProperty(SOURCE_FILE))
                .to(VENDOR_DELIVER);

        // dbo.usp_PostClaimPayment through sp_ClaimsDb_LedgerPost_WcfSql (RetryCount 0)
        from(LEDGER_POST).routeId("ledger.PostPayment")
                .to("sql:select ledger.post_claim_payment(:#${body})?outputType=SelectOne&outputHeader=ClaimsLedgerEntryId");

        // Ledger.ReversePayment with the msgLedgerPost the post was made with
        from(LEDGER_REVERSE).routeId("ledger.ReversePayment")
                .setBody(header(LEDGER_DOCUMENT_OPTION))
                .to("sql:select ledger.reverse_claim_payment(:#${body})?outputType=SelectOne&outputHeader=ClaimsLedgerEntryId");

        from(VENDOR_DELIVER).routeId("vendor.DeliverRemittance")
                .convertBodyTo(String.class, StandardCharsets.US_ASCII.name())
                .process(e -> TrailerTotalsGuard.check(e.getMessage().getBody(String.class)))
                .process(e -> e.getMessage().setHeader(Exchange.FILE_NAME, "REM_" + BTS2000.format(ZonedDateTime.now(ZoneOffset.UTC)) + "_"
                        + e.getMessage().getHeader(Exchange.FILE_NAME, String.class) + ".txt"))
                .setProperty(ATTEMPTS, constant(0))
                .setProperty(DELIVERED, constant(false))
                .loopDoWhile(e -> !e.getProperty(DELIVERED, Boolean.class) && e.getProperty(ATTEMPTS, Integer.class) < attempts)
                    .process(e -> e.setProperty(ATTEMPTS, e.getProperty(ATTEMPTS, Integer.class) + 1))
                    .bean(VendorServiceWindow.class, "awaitOpen")
                    .doTry()
                        .toD("sftp://{{claims.payment.vendor.host}}:{{claims.payment.vendor.port}}/{{claims.payment.vendor.directory}}"
                                + "?username={{claims.payment.vendor.username}}"
                                + "&privateKeyFile={{claims.payment.vendor.private-key-file}}"
                                + "&knownHostsFile={{claims.payment.vendor.known-hosts-file}}"
                                + "&strictHostKeyChecking=yes&useUserKnownHostsFile=false"
                                + "&tempFileName={{claims.payment.vendor.temporary-folder}}/$simple{file:onlyname}"
                                + "&fileExist=Ignore&binary=true&disconnect=true"
                                + "&maximumReconnectAttempts=0&connectTimeout=10000&jschLoggingLevel=WARN")
                        .setProperty(DELIVERED, constant(true))
                    .doCatch(Exception.class)
                        // catch (DeliveryFailureException) { delay new System.TimeSpan(0, 10, 0); }
                        .process(e -> {
                            e.setProperty(LAST_FAILURE, e.getProperty(Exchange.EXCEPTION_CAUGHT));
                            Thread.sleep(retryDelay.toMillis());
                        })
                    .end()
                .end()
                .process(e -> {
                    if (!e.getProperty(DELIVERED, Boolean.class)) {
                        String header = e.getMessage().getBody(String.class);
                        String instructionId = header.length() >= 43 ? header.substring(27, 43).trim() : "";
                        throw new VendorUnreachableException(instructionId, e.getProperty(ATTEMPTS, Integer.class),
                                e.getProperty(LAST_FAILURE, Throwable.class));
                    }
                });

        // sp_Ops_PaymentHeld_SMTP; runs after the saga has compensated
        from(OPS_NOTIFY).routeId("ops.PaymentHeld")
                .process(e -> {
                    OpsMail.Note note = OpsMail.paymentHeld(e.getProperty(INSTRUCTION, String.class), e.getProperty(ATTEMPTS, Integer.class));
                    e.getMessage().removeHeaders("*");
                    e.getMessage().setHeader("Subject", note.subject());
                    e.getMessage().setBody(note.body());
                })
                .to("smtp://{{claims.ops.smtp.host}}:{{claims.ops.smtp.port}}?from={{claims.ops.from}}&to={{claims.ops.to}}"
                        + "&contentType=text/plain");
    }
}
