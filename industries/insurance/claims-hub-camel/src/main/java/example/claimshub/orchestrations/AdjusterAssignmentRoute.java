package example.claimshub.orchestrations;


import jakarta.activation.DataHandler;
import jakarta.mail.util.ByteArrayDataSource;

import org.apache.camel.Exchange;
import org.apache.camel.attachment.AttachmentMessage;
import org.apache.camel.attachment.DefaultAttachment;
import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;
import example.claimshub.OrchestrationEndpoints;

/**
 * {@code Orchestrations/AdjusterAssignment.odx}. The parallel shape is a multicast whose aggregation strategy
 * waits for both branches: the roster (map to RosterQuery, then the roster procedure over JDBC, which
 * replaces the WCF-SQL port) and the archive copy (a folder, which replaces the FILE port). Only then is the
 * notice built from roster and request and sent over SMTP, as {@code Send_Notice} was.
 */
@Component
public class AdjusterAssignmentRoute extends RouteBuilder {

    public static final String NAME = "AdjusterAssignment";
    public static final String NS = "http://schemas.thistlecombe.example/claims/assignment";
    public static final String REQUEST_ID = "ClaimsHub.RequestId";
    public static final String ESCALATED = "ClaimsHub.Escalated";
    static final String REQUEST = "ClaimsHub.AssignmentRequest";
    static final String BRANCH = "ClaimsHub.ParallelBranch";
    static final String ROSTER_BRANCH = "roster";
    static final String NOTICE_BODY = "ClaimsHub.NoticeBody";
    static final String ROSTER_RECEIVED = "ClaimsHub.RosterReceived";
    /** RequestId names the compliance archive record and the notice attachment, so it must be one plain id. */
    static final String REQUEST_ID_PATTERN = "ASG-[0-9]{6}";

    static final String ROSTER_SQL = "SELECT * FROM usp_get_adjuster_roster(:?Region, :?Skill, CAST(:?AsOfDt AS date))";

    @Override
    public void configure() {
        from(OrchestrationEndpoints.of(NAME)).routeId(OrchestrationEndpoints.routeId(NAME))
            .convertBodyTo(byte[].class)
            .setProperty(REQUEST, body())
            .setProperty(REQUEST_ID, xpath("string(/*/RequestId)", String.class))
            .validate(exchangeProperty(REQUEST_ID).regex(REQUEST_ID_PATTERN))
            .multicast(new AssignmentAggregationStrategy()).parallelProcessing().stopOnException()
                .pipeline()
                    .to(MapEndpoints.of("AssignmentRequest_to_RosterQuery"))
                    .setHeader("Region", xpath("string(/*/Region)", String.class))
                    .setHeader("Skill", xpath("string(/*/Skill)", String.class))
                    .setHeader("AsOfDt", xpath("string(/*/AsOfDt)", String.class))
                    .setBody(constant(ROSTER_SQL))
                    .to("jdbc:dataSource?useHeadersAsParameters=true")
                    .process(e -> e.getMessage().setBody(RosterResultXml.of(e.getMessage().getBody(java.util.List.class))))
                    .setProperty(BRANCH, constant(ROSTER_BRANCH))
                .end()
                .pipeline()
                    .to("file:{{claimshub.archive.dir}}?fileExist=Fail&fileName=${exchangeProperty." + REQUEST_ID + "}.xml")
                .end()
            .end()
            .process(e -> {
                if (!e.getProperty(ROSTER_RECEIVED, false, Boolean.class)) {
                    throw new IllegalStateException(e.getProperty(REQUEST_ID) + ": the roster branch returned no RosterResult");
                }
            })
            .to(MapEndpoints.of("Roster_AssignmentRequest_to_Notice"))
            .convertBodyTo(byte[].class)
            .setProperty(ESCALATED, xpath("string(/*/Escalated) = 'true'", Boolean.class))
            .removeHeaders("*")
            .setHeader("To", xpath("string(/*/To)", String.class))
            .setHeader("Subject", xpath("string(/*/Subject)", String.class))
            .setProperty(NOTICE_BODY, xpath("string(/*/Body)", String.class))
            .process(AdjusterAssignmentRoute::bodyTextAndNoticeAttachment)
            .to("smtp://{{claimshub.smtp.host}}:{{claimshub.smtp.port}}?from={{claimshub.smtp.from}}"
                    + "&contentType=RAW(text/plain; charset=UTF-8)")
            .setBody(exchangeProperty("ClaimsHub.Notice"));
    }

    /** The SMTP adapter sent ClaimsHub.NoticeBody as the text and the notice itself as the one attachment. */
    static void bodyTextAndNoticeAttachment(Exchange e) throws Exception {
        byte[] notice = e.getMessage().getBody(byte[].class);
        e.setProperty("ClaimsHub.Notice", notice);
        String text = e.getProperty(NOTICE_BODY, String.class);
        DefaultAttachment attachment = new DefaultAttachment(new DataHandler(new ByteArrayDataSource(notice, "application/xml")));
        attachment.setHeader("Content-Transfer-Encoding", "base64");
        AttachmentMessage message = e.getMessage(AttachmentMessage.class);
        message.addAttachmentObject(e.getProperty(REQUEST_ID, String.class) + ".xml", attachment);
        message.setBody(text);
    }
}
