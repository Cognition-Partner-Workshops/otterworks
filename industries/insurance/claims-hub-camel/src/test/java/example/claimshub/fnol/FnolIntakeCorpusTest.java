package example.claimshub.fnol;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.fail;
import static org.junit.jupiter.api.DynamicTest.dynamicTest;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import org.apache.camel.Exchange;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import example.claimshub.golden.ByteComparison;

/**
 * The 16 corpus FNOLs through FnolIntake, end to end, against the shapes of the XLANG/s and the goldens the
 * BizTalk side produced. Writes {@code target/fnol-parity/REPORT.md}, one row per claim.
 */
@DisplayName("FnolIntake over the 16 corpus FNOLs")
class FnolIntakeCorpusTest extends FnolIntakeTestBase {

    static final String DECLINE = "DECLINE_NOT_IN_FORCE";
    static final String FRAUD = "FRAUD_REVIEW";
    static final String FAST_TRACK = "FAST_TRACK";

    static final String FRAUD_DIR = "fraud-desk/referrals";
    static final String DECLINES_DIR = "agency-liaison/declines";
    static final String GLASS_DIR = "glassnet/thistlecombe/fasttrack";

    private static final Pattern CLAIM_ROW = Pattern.compile("^\\|\\s*(CLM-[0-9-]+)\\s*\\|\\s*([A-Z_]+)\\s*\\|.*$", Pattern.MULTILINE);
    private static final Pattern TOTAL_ROW = Pattern.compile("^\\|\\s*([A-Z_]+)\\s*\\|\\s*(\\d+)\\s*\\|\\s*$", Pattern.MULTILINE);

    record Expected(String claim, String outcome, String agencyId, String lossCause) {
        boolean inserted() {
            return !DECLINE.equals(outcome);
        }

        boolean assigned() {
            return inserted() && !FAST_TRACK.equals(outcome);
        }

        String routedTo() {
            return switch (outcome) {
                case FRAUD -> FRAUD_DIR + "/" + claim + ".xml";
                case DECLINE -> DECLINES_DIR + "/" + agencyId + "/" + claim + ".xml";
                case FAST_TRACK -> "GLAS".equals(lossCause) ? GLASS_DIR + "/" + claim + ".xml" : "-";
                default -> "-";
            };
        }
    }

    private final Map<String, Expected> expected = loadExpected();

    private Map<String, Exchange> instances;
    private Throwable runFailure;

    private synchronized Map<String, Exchange> run() {
        if (instances == null && runFailure == null) {
            try {
                reset();
                completed().expectedMessageCount(expected.size());
                for (Path fnol : fnolInputs()) {
                    send(read(fnol));
                }
                completed().setResultWaitTime(WINDOW.plusSeconds(60).toMillis());
                completed().assertIsSatisfied();
                instances = completed().getExchanges().stream()
                        .collect(Collectors.toMap(FnolIntakeTestBase::claimNumber, Function.identity(), (a, b) -> a, TreeMap::new));
            } catch (Throwable e) {
                runFailure = e;
            }
        }
        if (runFailure != null) {
            fail("the 16 FNOLs did not run through FnolIntake: " + runFailure, runFailure);
        }
        return instances;
    }

    private Exchange instance(String claim) {
        Exchange exchange = run().get(claim);
        assertThat(exchange).as("no completed FnolIntake instance for " + claim).isNotNull();
        return exchange;
    }

    @Test
    @DisplayName("the corpus is the 16 FNOLs SUMMARY.md lists")
    void corpusMatchesSummary() {
        assertThat(fnolInputs()).hasSize(16);
        assertThat(expected).hasSize(16);
        assertThat(fnolInputs()).extracting(p -> p.getFileName().toString().replace(".xml", ""))
                .containsExactlyElementsOf(expected.keySet());
    }

    @TestFactory
    @DisplayName("Construct_PolicyRq: the policy is looked up as of the loss date")
    List<DynamicTest> policyLookupAsOfLossDate() {
        return perClaim(claim -> {
            Exchange instance = instance(claim);
            assertBytes("policy-inq-rq", claim, instance.getProperty("msgPolicyRq", String.class));
            String rs = instance.getProperty("msgPolicyRs", String.class);
            assertThat(rs).as("msgPolicyRs").isNotBlank();
            String stub = read(fixture("corpus/stubs/policy/" + policyNumber(claim) + ".xml"));
            assertThat(tag(rs, "PolicyStatusCd")).as("policy status the WCF-SQL port answered").isEqualTo(tag(stub, "PolicyStatusCd"));
        });
    }

    @Test
    @DisplayName("usp_GetPolicyAsOf stand-in: " + LegacySystems.AS_OF_POLICY + " was cancelled between the loss and the report")
    void policyStandInDistinguishesLossAndReportDates() throws Exception {
        LegacySystems.postgres();
        assertThat(lookUp(LegacySystems.AS_OF_POLICY, "2026-09-15")).as("as of the loss date").isEqualTo("Active");
        assertThat(lookUp(LegacySystems.AS_OF_POLICY, "2026-09-29")).as("as of the reported date").isEqualTo("Cancelled");
        assertThat(LegacySystems.claims()).isNotNull();
        Exchange instance = instance("CLM-2026-100409");
        assertThat(tag(instance.getProperty("msgPolicyRs", String.class), "PolicyStatusCd")).isEqualTo("Active");
        assertThat(instance.getProperty("triageOutcome", String.class)).isEqualTo("STANDARD");
    }

    @TestFactory
    @DisplayName("Construct_InsertClaim: the two-source map over msgClaim and msgPolicyRs")
    List<DynamicTest> insertClaimTwoSourceMap() {
        return perClaim(claim -> {
            Exchange instance = instance(claim);
            assertBytes("fnol-canonical", claim, instance.getProperty("msgClaim", String.class));
            assertBytes("insert-claim", claim, instance.getProperty("msgInsertClaim", String.class));
            assertBytes("triage-facts", claim, instance.getProperty("msgTriageFacts", String.class));
        });
    }

    @TestFactory
    @DisplayName("Call_Rules ClaimTriage: the outcome the policy gave")
    List<DynamicTest> triageCall() {
        return perClaim(claim -> assertThat(instance(claim).getProperty("triageOutcome", String.class))
                .isEqualTo(expected.get(claim).outcome()));
    }

    @TestFactory
    @DisplayName("Decide_Outcome: a declined policy is never inserted; everything else is, with its outcome")
    List<DynamicTest> declinesAreNeverInserted() {
        return perClaim(claim -> {
            Expected e = expected.get(claim);
            Exchange instance = instance(claim);
            Map<String, LegacySystems.ClaimRow> rows = claimRows();
            if (e.inserted()) {
                assertThat(instance.getMessage().getHeader("FnolStatus", String.class)).isEqualTo("COMPLETED");
                assertThat(rows).containsKey(claim);
                assertThat(rows.get(claim).triageOutcome()).isEqualTo(e.outcome());
            } else {
                assertThat(instance.getMessage().getHeader("FnolStatus", String.class)).isEqualTo("TERMINATED");
                assertThat(rows).doesNotContainKey(claim);
            }
        });
    }

    @Test
    @DisplayName("Decide_Assignment: fast-track claims skip adjuster assignment")
    void fastTrackSkipsAssignment() {
        run();
        Set<String> wanted = expected.values().stream().filter(Expected::assigned).map(Expected::claim).collect(Collectors.toCollection(TreeSet::new));
        assertThat(assigned()).containsExactlyElementsOf(wanted);
    }

    @Test
    @DisplayName("sp_Fraud_Referral_FILE: TriageFacts with TriageOutcome = FRAUD_REVIEW go to the fraud desk")
    void fraudReferralRoute() {
        run();
        assertRouted(FRAUD_DIR, FRAUD, "TriageFacts");
    }

    @Test
    @DisplayName("sp_Declines_FILE: TriageFacts with TriageOutcome = DECLINE_NOT_IN_FORCE go to the agency's declines folder")
    void declineRoute() {
        run();
        assertRouted(DECLINES_DIR, DECLINE, "TriageFacts");
    }

    @Test
    @DisplayName("sp_GlassVendor_FastTrack_SFTP: usp_InsertClaim with FAST_TRACK and LossCauseCd = GLAS go to the glass network")
    void glassFastTrackRoute() {
        run();
        assertRouted(GLASS_DIR, FAST_TRACK, "usp_InsertClaim");
    }

    @Test
    @DisplayName("outcome totals match corpus/golden/triage/SUMMARY.md (4 declines, 3 fraud referrals, 4 fast tracks)")
    void totalsMatchSummary() {
        Map<String, Long> summary = summaryTotals();
        assertThat(summary).containsEntry(DECLINE, 4L).containsEntry(FRAUD, 3L).containsEntry(FAST_TRACK, 4L);
        Map<String, Long> actual = run().values().stream()
                .collect(Collectors.groupingBy(x -> x.getProperty("triageOutcome", String.class), TreeMap::new, Collectors.counting()));
        assertThat(actual).isEqualTo(summary);
        assertThat(outFiles(DECLINES_DIR)).hasSize(summary.get(DECLINE).intValue());
        assertThat(outFiles(FRAUD_DIR)).hasSize(summary.get(FRAUD).intValue());
        assertThat(claimRows().values().stream().filter(r -> FAST_TRACK.equals(r.triageOutcome())).count()).isEqualTo(summary.get(FAST_TRACK));
    }

    @AfterAll
    void writeReport() throws Exception {
        Path report = Path.of("target/fnol-parity/REPORT.md");
        Files.createDirectories(report.getParent());
        StringBuilder md = new StringBuilder("# FnolIntake parity, 16 corpus FNOLs\n\n");
        md.append("Source = BizTalk corpus goldens (`corpus/golden/triage`, the XLANG/s decide shapes, the binding's subscriptions). Target = the Camel route.\n\n");
        md.append("| Claim | Outcome (source) | Outcome (target) | Inserted (source / target) | Assignment (source / target) | Routed to (source) | Routed to (target) | Verdict | Cause |\n");
        md.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n");
        Map<String, LegacySystems.ClaimRow> rows = runFailure == null && instances != null ? claimRows() : Map.of();
        Set<String> assigned = instances != null ? assigned() : Set.of();
        List<String> routed = new ArrayList<>();
        for (String dir : List.of(FRAUD_DIR, DECLINES_DIR, GLASS_DIR)) {
            outFiles(dir).forEach(f -> routed.add(dir + "/" + f));
        }
        int pass = 0;
        for (Expected e : expected.values()) {
            Exchange x = instances == null ? null : instances.get(e.claim());
            String outcome = x == null ? "-" : x.getProperty("triageOutcome", String.class);
            boolean inserted = rows.containsKey(e.claim());
            boolean assignedNow = assigned.contains(e.claim());
            String target = routed.stream().filter(r -> r.endsWith("/" + e.claim() + ".xml")).collect(Collectors.joining(", "));
            target = target.isEmpty() ? "-" : target;
            List<String> causes = new ArrayList<>();
            if (x == null) {
                causes.add(runFailure != null ? "no instance: " + firstLine(runFailure) : "no instance completed");
            } else {
                if (!e.outcome().equals(outcome)) causes.add("outcome differs");
                if (e.inserted() != inserted) causes.add(e.inserted() ? "not inserted" : "inserted a declined policy");
                if (e.assigned() != assignedNow) causes.add(e.assigned() ? "no assignment request" : "assignment sent");
                if (!e.routedTo().equals(target)) causes.add("routing differs");
            }
            boolean ok = causes.isEmpty();
            pass += ok ? 1 : 0;
            md.append("| ").append(e.claim()).append(" | ").append(e.outcome()).append(" | ").append(outcome)
                    .append(" | ").append(yn(e.inserted())).append(" / ").append(x == null ? "-" : yn(inserted))
                    .append(" | ").append(yn(e.assigned())).append(" / ").append(x == null ? "-" : yn(assignedNow))
                    .append(" | ").append(e.routedTo()).append(" | ").append(target)
                    .append(" | ").append(ok ? "match" : "MISMATCH").append(" | ").append(ok ? "" : String.join("; ", causes)).append(" |\n");
        }
        md.append("\n| Outcome | Source | Target | Difference |\n| --- | --- | --- | --- |\n");
        Map<String, Long> source = summaryTotals();
        Map<String, Long> target = instances == null ? Map.of() : instances.values().stream()
                .collect(Collectors.groupingBy(x -> x.getProperty("triageOutcome", String.class), TreeMap::new, Collectors.counting()));
        for (var entry : source.entrySet()) {
            long t = target.getOrDefault(entry.getKey(), 0L);
            md.append("| ").append(entry.getKey()).append(" | ").append(entry.getValue()).append(" | ").append(t)
                    .append(" | ").append(t - entry.getValue()).append(" |\n");
        }
        md.append("\n**").append(pass).append(" of ").append(expected.size()).append(" claims match.**\n");
        Files.writeString(report, md.toString(), StandardCharsets.UTF_8);
    }

    private List<DynamicTest> perClaim(org.junit.jupiter.api.function.ThrowingConsumer<String> check) {
        return expected.keySet().stream().map(claim -> dynamicTest(claim, () -> check.accept(claim))).toList();
    }

    private void assertRouted(String dir, String outcome, String rootElement) {
        List<String> wanted = expected.values().stream()
                .filter(e -> e.routedTo().startsWith(dir + "/"))
                .map(e -> e.routedTo().substring(dir.length() + 1)).sorted().toList();
        assertThat(wanted).as("expected " + outcome + " routing").isNotEmpty();
        assertThat(outFiles(dir)).containsExactlyElementsOf(wanted);
        for (String file : wanted) {
            String body = read(OUT.resolve(dir).resolve(file));
            assertThat(body).as(file).contains(":" + rootElement + " ");
            assertThat(body).as(file).containsPattern("<(Outcome|TriageOutcome)>" + outcome + "<");
        }
    }

    private Set<String> assigned() {
        return assignment().getExchanges().stream().map(FnolIntakeTestBase::claimNumber).collect(Collectors.toCollection(TreeSet::new));
    }

    private static Map<String, LegacySystems.ClaimRow> claimRows() {
        return LegacySystems.claims().stream().collect(Collectors.toMap(LegacySystems.ClaimRow::claimNumber, Function.identity()));
    }

    private static void assertBytes(String goldenDir, String claim, String actual) {
        assertThat(actual).as(goldenDir + " for " + claim).isNotNull();
        byte[] golden = readBytes(fixture("corpus/golden/" + goldenDir + "/" + claim + ".xml"));
        ByteComparison diff = ByteComparison.of(golden, actual.getBytes(StandardCharsets.UTF_8));
        if (!diff.identical()) {
            fail(goldenDir + " for " + claim + " differs from the golden: " + diff.cause());
        }
    }

    private static String lookUp(String policy, String asOf) throws Exception {
        try (Connection c = LegacySystems.connect();
                PreparedStatement ps = c.prepareStatement(
                        "select (xpath('/*/PolicyStatusCd/text()', usp_get_policy_as_of(xmlparse(document ?))))[1]::text")) {
            ps.setString(1, "<ns0:PolicyInqRq xmlns:ns0=\"http://schemas.thistlecombe.example/acord/policy\"><RqUID>t</RqUID><PolicyNumber>"
                    + policy + "</PolicyNumber><AsOfDt>" + asOf + "</AsOfDt></ns0:PolicyInqRq>");
            try (ResultSet rs = ps.executeQuery()) {
                rs.next();
                return rs.getString(1);
            }
        }
    }

    private static Map<String, Expected> loadExpected() {
        String summary = read(fixture("corpus/golden/triage/SUMMARY.md"));
        ObjectMapper json = new ObjectMapper();
        Map<String, Expected> result = new LinkedHashMap<>();
        Matcher m = CLAIM_ROW.matcher(summary);
        while (m.find()) {
            String claim = m.group(1);
            try {
                JsonNode golden = json.readTree(read(fixture("corpus/golden/triage/" + claim + ".json")));
                assertThat(golden.get("Outcome").asText()).as(claim + " SUMMARY.md against its json").isEqualTo(m.group(2));
            } catch (java.io.IOException e) {
                throw new java.io.UncheckedIOException(e);
            }
            String insert = read(fixture("corpus/golden/insert-claim/" + claim + ".xml"));
            result.put(claim, new Expected(claim, m.group(2), tag(insert, "AgencyId"), tag(insert, "LossCause")));
        }
        return result;
    }

    private static Map<String, Long> summaryTotals() {
        Map<String, Long> totals = new TreeMap<>();
        Matcher m = TOTAL_ROW.matcher(read(fixture("corpus/golden/triage/SUMMARY.md")));
        while (m.find()) {
            totals.put(m.group(1), Long.parseLong(m.group(2)));
        }
        return totals;
    }

    private static String policyNumber(String claim) {
        return tag(read(fixture("corpus/golden/insert-claim/" + claim + ".xml")), "PolicyNumber");
    }

    static String tag(String xml, String name) {
        Matcher m = Pattern.compile("<" + name + ">([^<]*)</" + name + ">").matcher(xml);
        return m.find() ? m.group(1) : null;
    }

    private static byte[] readBytes(Path path) {
        try {
            return Files.readAllBytes(path);
        } catch (java.io.IOException e) {
            throw new java.io.UncheckedIOException(e);
        }
    }

    private static String yn(boolean b) {
        return b ? "yes" : "no";
    }

    private static String firstLine(Throwable t) {
        String s = String.valueOf(t.getMessage());
        int nl = s.indexOf('\n');
        return (nl < 0 ? s : s.substring(0, nl)).replace("|", "/");
    }
}
