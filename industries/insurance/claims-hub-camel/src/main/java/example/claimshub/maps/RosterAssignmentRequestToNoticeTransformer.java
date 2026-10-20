package example.claimshub.maps;

import static example.claimshub.maps.AggregateEnvelope.text;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

import org.w3c.dom.Element;

/**
 * BizTalk map {@code Roster_AssignmentRequest_to_Notice}: the roster result (part 0) and the assignment
 * request (part 1) become the adjuster notice.
 *
 * <p>Eligible means available, same region, the required skill in the comma-separated skill list and
 * open claims below the maximum. The fewest open claims wins, ties broken by adjuster id (code-point
 * order, the XSLT default collation). SLA is 1, 3 or 7 days for HIGH, MED and anything else. With
 * nobody eligible the notice escalates to the claims supervisor. The estimate is copied as text, not
 * reformatted.
 */
public final class RosterAssignmentRequestToNoticeTransformer {

    static final String ASSIGNMENT_NS = "http://schemas.thistlecombe.example/claims/assignment";
    static final String SUPERVISOR = "claims.supervisor@thistlecombe.example";
    static final String ROOT_OPEN = "<ns0:AssignmentNotice xmlns:ns0=\"" + ASSIGNMENT_NS + "\">";
    static final String ROOT_CLOSE = "</ns0:AssignmentNotice>";

    private record Candidate(Element adjuster, BigDecimal openClaims, String id) {
    }

    private static final Comparator<Candidate> LEAST_LOADED = Comparator
            .comparing(Candidate::openClaims, Comparator.nullsFirst(Comparator.naturalOrder()))
            .thenComparing(Candidate::id);

    public byte[] transform(byte[] source) {
        AggregateEnvelope envelope = AggregateEnvelope.parse(source);
        Element roster = envelope.part(0, ASSIGNMENT_NS, "RosterResult");
        Element req = envelope.part(1, ASSIGNMENT_NS, "AssignmentRequest");

        String skill = text(req, "RequiredSkill");
        String region = text(req, "Region");
        String severity = text(req, "Severity");
        String claimNumber = text(req, "ClaimNumber");
        String sla = switch (severity) {
            case "HIGH" -> "1";
            case "MED" -> "3";
            default -> "7";
        };

        List<Element> adjusters = AggregateEnvelope.children(roster, "Adjuster");
        boolean hasRequest = req != null && AggregateEnvelope.child(req, null, "Region") != null;
        Optional<Candidate> chosen = adjusters.stream()
                .filter(a -> "true".equals(text(a, "Available")))
                .filter(a -> hasRequest && region.equals(text(a, "Region")))
                .filter(a -> ("," + text(a, "Skills") + ",").contains("," + skill + ","))
                .filter(a -> lessThan(ClaimPolicyInqRsToInsertClaimTransformer.number(text(a, "OpenClaims")),
                        ClaimPolicyInqRsToInsertClaimTransformer.number(text(a, "MaxClaims"))))
                .map(a -> new Candidate(a, ClaimPolicyInqRsToInsertClaimTransformer.number(text(a, "OpenClaims")), text(a, "AdjusterId")))
                .min(LEAST_LOADED);

        SaxonXmlWriter w = new SaxonXmlWriter().raw(ROOT_OPEN);
        if (chosen.isPresent()) {
            Element a = chosen.get().adjuster();
            String name = text(a, "Name");
            w.element("To", text(a, "Email"))
                    .element("Subject", "Claim " + claimNumber + " assigned: " + text(req, "LossCause") + " (" + severity + ")")
                    .element("ClaimNumber", claimNumber)
                    .element("AdjusterId", text(a, "AdjusterId"))
                    .element("AdjusterName", name)
                    .element("Severity", severity)
                    .element("SlaDays", sla)
                    .element("Body", name + ", claim " + claimNumber + " for " + text(req, "ClaimantName")
                            + " (" + text(req, "LineOfBusiness") + ", " + text(req, "LossCause")
                            + ", estimate " + text(req, "EstimatedAmount") + ") is yours. First contact within "
                            + sla + " day(s) of " + text(req, "RequestedDt") + ".")
                    .element("Escalated", "false");
        } else {
            w.element("To", SUPERVISOR)
                    .element("Subject", "Claim " + claimNumber + " needs an adjuster: no capacity in " + region + " for " + skill)
                    .element("ClaimNumber", claimNumber)
                    .element("AdjusterId", "UNASSIGNED")
                    .element("AdjusterName", "Unassigned")
                    .element("Severity", severity)
                    .element("SlaDays", sla)
                    .element("Body", "No available adjuster in " + region + " holds " + skill + ". Claim " + claimNumber
                            + " for " + text(req, "ClaimantName") + " waits for manual assignment; SLA is " + sla
                            + " day(s) from " + text(req, "RequestedDt") + ".")
                    .element("Escalated", "true");
        }
        return w.raw(ROOT_CLOSE).toString().getBytes(StandardCharsets.UTF_8);
    }

    private static boolean lessThan(BigDecimal a, BigDecimal b) {
        return a != null && b != null && a.compareTo(b) < 0;
    }
}
