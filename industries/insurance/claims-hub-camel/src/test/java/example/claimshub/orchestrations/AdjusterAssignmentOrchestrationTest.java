package example.claimshub.orchestrations;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.fail;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Stream;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.builder.AdviceWith;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.wait.strategy.Wait;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import example.claimshub.ClaimsHubApplication;
import example.claimshub.OrchestrationEndpoints;
import example.claimshub.golden.ByteComparison;
import example.claimshub.golden.CorpusManifest;
import jakarta.mail.BodyPart;
import jakarta.mail.Multipart;
import jakarta.mail.Part;
import jakarta.mail.Session;
import jakarta.mail.internet.MimeMessage;

/**
 * Characterization of {@code Orchestrations/AdjusterAssignment.odx}, end to end: the ten corpus requests go
 * through the orchestration route with the roster port on PostgreSQL 16 (seeded from
 * {@code corpus/stubs/roster}), the archive port on a folder and the notice port on MailHog. The archive
 * write is held back 400 ms, so a notice that does not wait for both parallel branches is caught.
 */
@SpringBootTest(classes = ClaimsHubApplication.class, properties = "camel.springboot.main-run-controller=false")
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class AdjusterAssignmentOrchestrationTest {

    static final String ORCHESTRATION = "AdjusterAssignment";
    static final String REQUEST_ID = "ClaimsHub.RequestId";
    static final String SUPERVISOR = "claims.supervisor@thistlecombe.example";
    static final List<String> ESCALATIONS = List.of("ASG-520104", "ASG-520108");

    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16").withDatabaseName("claimscore");
    static final GenericContainer<?> MAILHOG = new GenericContainer<>("mailhog/mailhog:v1.0.1")
            .withExposedPorts(1025, 8025).waitingFor(Wait.forHttp("/api/v2/messages").forPort(8025));
    static final Path ARCHIVE;

    static {
        POSTGRES.start();
        MAILHOG.start();
        try {
            RosterStubSeed.load(CorpusManifest.fixtureDir(), POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
            ARCHIVE = Files.createTempDirectory("assignment-archive");
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    @DynamicPropertySource
    static void ports(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("claimshub.smtp.host", MAILHOG::getHost);
        registry.add("claimshub.smtp.port", () -> MAILHOG.getMappedPort(1025));
        registry.add("claimshub.archive.dir", ARCHIVE::toString);
    }

    record Event(String what, long at) {
    }

    record Mail(List<String> envelopeTo, String to, String subject, String text, byte[] notice) {
    }

    record Run(Map<String, byte[]> requests, Map<String, List<Event>> events, Map<String, Map<String, Object>> rosterQuery,
            Map<String, List<Map<String, Object>>> rosterRows, Map<String, Mail> mailByClaim) {
    }

    @Autowired
    CamelContext camelContext;

    @Autowired
    ProducerTemplate producer;

    private Run run;
    private Throwable runFailure;
    private final List<String[]> reportRows = new ArrayList<>();

    private synchronized Run corpus() {
        if (run == null && runFailure == null) {
            try {
                run = execute();
            } catch (Throwable t) {
                runFailure = t;
            }
        }
        if (runFailure != null) {
            fail(runFailure.getMessage(), runFailure);
        }
        return run;
    }

    private Run execute() throws Exception {
        String routeId = OrchestrationEndpoints.routeId(ORCHESTRATION);
        if (camelContext.getRoute(routeId) == null) {
            fail("no route " + routeId + " consuming " + OrchestrationEndpoints.of(ORCHESTRATION));
        }
        Map<String, List<Event>> events = new ConcurrentHashMap<>();
        Map<String, Map<String, Object>> query = new ConcurrentHashMap<>();
        Map<String, List<Map<String, Object>>> rows = new ConcurrentHashMap<>();
        AdviceWith.adviceWith(camelContext, routeId, a -> {
            a.weaveByToUri("jdbc:*").before().process(e -> {
                query.put(id(e), Map.of("Region", e.getIn().getHeader("Region"), "Skill", e.getIn().getHeader("Skill"),
                        "AsOfDt", e.getIn().getHeader("AsOfDt")));
                event(events, e, "roster-start");
            });
            a.weaveByToUri("jdbc:*").after().process(e -> {
                rows.put(id(e), e.getIn().getBody(List.class));
                event(events, e, "roster-done");
            });
            a.weaveByToUri("file:*").before().process(e -> event(events, e, "archive-start")).delay(400);
            a.weaveByToUri("file:*").after().process(e -> event(events, e, "archive-done"));
            a.weaveByToUri("smtp*").before().process(e -> event(events, e, "notice-send"));
        });
        Map<String, byte[]> requests = new LinkedHashMap<>();
        for (Path input : inputs()) {
            byte[] body = Files.readAllBytes(input);
            requests.put(stem(input), body);
            Exchange result = producer.request(OrchestrationEndpoints.of(ORCHESTRATION), e -> e.getIn().setBody(body));
            if (result.getException() != null) {
                throw new IllegalStateException(stem(input) + ": " + result.getException().getMessage(), result.getException());
            }
        }
        return new Run(requests, events, query, rows, mails(requests.size()));
    }

    // 1. Parallel_Actions: both branches finish before Send_Notice.
    @Test
    void bothParallelBranchesCompleteBeforeTheNoticeIsSent() {
        Run r = corpus();
        for (String id : r.requests().keySet()) {
            List<Event> ev = r.events().get(id);
            assertThat(ev).as(id).isNotNull();
            long notice = at(ev, "notice-send", id);
            assertThat(at(ev, "roster-done", id)).as(id + " roster before notice").isLessThan(notice);
            assertThat(at(ev, "archive-done", id)).as(id + " archive before notice").isLessThan(notice);
            assertThat(at(ev, "roster-start", id)).as(id + " roster runs alongside the held archive write").isLessThan(at(ev, "archive-done", id));
        }
    }

    // 2. Branch 2: the archive copy exists for every request, the escalated ones included.
    @Test
    void theArchiveHoldsACopyOfEveryRequestIncludingEscalations() throws IOException {
        Run r = corpus();
        List<byte[]> archived;
        try (Stream<Path> files = Files.walk(ARCHIVE)) {
            archived = files.filter(Files::isRegularFile).filter(p -> !p.getFileName().toString().startsWith("."))
                    .map(AdjusterAssignmentOrchestrationTest::read).toList();
        }
        assertThat(archived).hasSize(r.requests().size());
        r.requests().forEach((id, body) -> assertThat(archived.stream().filter(a -> Arrays.equals(a, body)).count())
                .as(id + " archived once, byte for byte").isEqualTo(1));
        assertThat(r.requests().keySet()).containsAll(ESCALATIONS);
    }

    // 3. Branch 1: AssignmentRequest_to_RosterQuery, then the roster port by region and skill as of RequestedDt.
    @Test
    void theRosterIsQueriedByRegionAndSkillAsOfTheRequestDate() throws Exception {
        Run r = corpus();
        Path fixture = CorpusManifest.fixtureDir();
        for (String id : r.requests().keySet()) {
            String golden = Files.readString(fixture.resolve("corpus/golden/roster-query/" + id + ".xml"));
            Map<String, Object> q = r.rosterQuery().get(id);
            assertThat(q).as(id).isNotNull();
            assertThat(String.valueOf(q.get("Region"))).as(id).isEqualTo(between(golden, "Region"));
            assertThat(String.valueOf(q.get("Skill"))).as(id).isEqualTo(between(golden, "Skill"));
            assertThat(String.valueOf(q.get("AsOfDt"))).as(id).isEqualTo(between(golden, "AsOfDt"));
            List<RosterStubSeed.Adjuster> answered = r.rosterRows().get(id).stream().map(m -> new RosterStubSeed.Adjuster(
                    (String) m.get("adjuster_id"), (String) m.get("name"), (String) m.get("email"), (String) m.get("region"),
                    (String) m.get("skills"), ((Number) m.get("open_claims")).intValue(), ((Number) m.get("max_claims")).intValue(),
                    (Boolean) m.get("available"))).toList();
            assertThat(answered).as(id + " roster as the stub answered it").isEqualTo(RosterStubSeed.adjusters(fixture.resolve("corpus/stubs/roster/" + id + ".xml")));
        }
        // ADJ-102's caseload grows request by request; only the as-of snapshot gives ASG-520109 its 16.
        assertThat(r.rosterRows().get("ASG-520109")).anyMatch(m -> "ADJ-102".equals(m.get("adjuster_id")) && ((Number) m.get("open_claims")).intValue() == 16);
    }

    // 4. Construct_Notice: least loaded eligible adjuster wins, ties by id.
    @Test
    void theLeastLoadedEligibleAdjusterWins() {
        Run r = corpus();
        assertThat(notice(r, "ASG-520106")).contains("<AdjusterId>ADJ-105</AdjusterId>"); // 7 open beats ADJ-104's 14
        assertThat(notice(r, "ASG-520109")).contains("<AdjusterId>ADJ-101</AdjusterId>"); // 11 beats ADJ-102's 16 that day
        assertThat(notice(r, "ASG-520103")).contains("<AdjusterId>ADJ-108</AdjusterId>"); // ADJ-107 has 3 but is unavailable
        assertThat(notice(r, "ASG-520102")).contains("<AdjusterId>ADJ-103</AdjusterId>"); // 19 of 20 is still under the cap
    }

    // 5. No eligible adjuster: the notice escalates to the supervisor with Escalated true.
    @Test
    void nobodyEligibleEscalatesToTheSupervisor() {
        Run r = corpus();
        for (String id : r.requests().keySet()) {
            Mail mail = mail(r, id);
            boolean escalated = ESCALATIONS.contains(id);
            assertThat(mail.envelopeTo()).as(id).containsExactly(escalated ? SUPERVISOR : between(notice(r, id), "To"));
            assertThat(notice(r, id)).as(id).contains("<Escalated>" + escalated + "</Escalated>");
            if (escalated) {
                assertThat(notice(r, id)).contains("<To>" + SUPERVISOR + "</To>").contains("<AdjusterId>UNASSIGNED</AdjusterId>");
            }
        }
    }

    // 6. SLA days by severity.
    @Test
    void slaDaysAreOneThreeAndSevenBySeverity() {
        Run r = corpus();
        Map<String, String> sla = Map.of("HIGH", "1", "MED", "3", "LOW", "7");
        r.requests().forEach((id, body) -> {
            String severity = between(new String(body, StandardCharsets.UTF_8), "Severity");
            assertThat(between(notice(r, id), "SlaDays")).as(id + " " + severity).isEqualTo(sla.get(severity));
        });
    }

    // Send_Notice: the SMTP port takes To, Subject and the body text from the notice and attaches the notice.
    @Test
    void theMailCarriesToSubjectAndBodyFromTheNotice() {
        Run r = corpus();
        for (String id : r.requests().keySet()) {
            Mail mail = mail(r, id);
            String notice = notice(r, id);
            assertThat(mail.to()).as(id).isEqualTo(between(notice, "To"));
            assertThat(mail.subject()).as(id).isEqualTo(between(notice, "Subject"));
            assertThat(mail.text().strip()).as(id).isEqualTo(between(notice, "Body"));
        }
    }

    // 7. The notice each request produces is byte-identical to corpus/golden/assignment-notice.
    @TestFactory
    Stream<DynamicTest> noticesAreByteIdenticalToTheGoldens() {
        return inputs().stream().map(input -> DynamicTest.dynamicTest(stem(input), () -> {
            String id = stem(input);
            byte[] golden = Files.readAllBytes(CorpusManifest.fixtureDir().resolve("corpus/golden/assignment-notice/" + id + ".xml"));
            ByteComparison cmp;
            byte[] actual;
            try {
                actual = mail(corpus(), id).notice();
                cmp = ByteComparison.of(golden, actual);
            } catch (Throwable t) {
                reportRows.add(new String[] {id, digest(golden), "none", "no notice", "red", firstLine(t.getMessage())});
                throw t;
            }
            reportRows.add(new String[] {id, digest(golden), digest(actual), cmp.identical() ? "0 bytes" : "differs",
                    cmp.identical() ? "green" : "red", cmp.cause()});
            if (!cmp.identical()) {
                fail(id + ": " + cmp.cause());
            }
        }));
    }

    // RequestId names the compliance archive copy and the notice attachment. One that is not ASG-nnnnnn, or that
    // is already archived, is refused: no archive record is written or replaced and no notice is mailed.
    @TestFactory
    Stream<DynamicTest> aRequestIdThatCannotNameItsOwnArchiveRecordIsRefused() {
        Map<String, String> cases = new LinkedHashMap<>();
        cases.put("empty", "");
        cases.put("sub-folder", "2026/ASG-520100");
        cases.put("parent-folder", "../ASG-520100");
        cases.put("lower-case", "asg-520100");
        cases.put("padded", " ASG-520100");
        cases.put("already archived", "ASG-520101");
        return cases.entrySet().stream().map(c -> DynamicTest.dynamicTest(c.getKey(), () -> {
            Run r = corpus();
            String original = new String(r.requests().get("ASG-520100"), StandardCharsets.UTF_8);
            byte[] tampered = original.replace("<RequestId>ASG-520100</RequestId>", "<RequestId>" + c.getValue() + "</RequestId>")
                    .replace("Imogen Castellanos", "Tampered Record").getBytes(StandardCharsets.UTF_8);
            Map<Path, String> archiveBefore = archive();
            int mailsBefore = mailCount();
            Exchange result = producer.request(OrchestrationEndpoints.of(ORCHESTRATION), e -> e.getIn().setBody(tampered));
            assertThat(result.getException()).as(c.getKey() + " refused").isNotNull();
            assertThat(archive()).as(c.getKey() + " archive untouched").isEqualTo(archiveBefore);
            assertThat(mailCount()).as(c.getKey() + " no notice mailed").isEqualTo(mailsBefore);
        }));
    }

    private static Map<Path, String> archive() throws IOException {
        try (Stream<Path> files = Files.walk(ARCHIVE)) {
            Map<Path, String> snapshot = new java.util.TreeMap<>();
            files.filter(Files::isRegularFile).forEach(p -> snapshot.put(ARCHIVE.relativize(p), digest(read(p))));
            return snapshot;
        }
    }

    private static int mailCount() throws Exception {
        URI api = URI.create("http://" + MAILHOG.getHost() + ":" + MAILHOG.getMappedPort(8025) + "/api/v2/messages?limit=1");
        String json = HttpClient.newHttpClient().send(HttpRequest.newBuilder(api).build(), HttpResponse.BodyHandlers.ofString()).body();
        return new ObjectMapper().readTree(json).get("total").asInt();
    }

    @AfterAll
    void writeReport() throws IOException {
        Path dir = Path.of("target", "golden-report");
        Files.createDirectories(dir);
        StringBuilder md = new StringBuilder("| Request | Golden notice (BizTalk) | Camel notice | Difference | Verdict | Cause |\n"
                + "| --- | --- | --- | --- | --- | --- |\n");
        long green = 0;
        for (String[] row : reportRows) {
            md.append("|");
            for (String cell : row) {
                md.append(' ').append(cell == null ? "" : cell.replace("|", "\\|")).append(" |");
            }
            md.append('\n');
            green += "green".equals(row[4]) ? 1 : 0;
        }
        md.append("| **Total** | ").append(reportRows.size()).append(" | ").append(reportRows.size()).append(" | | **")
                .append(green).append(" green, ").append(reportRows.size() - green).append(" red** | |\n");
        Files.writeString(dir.resolve(ORCHESTRATION + ".md"), md.toString());
    }

    private static List<Path> inputs() {
        try (Stream<Path> files = Files.list(CorpusManifest.fixtureDir().resolve("corpus/inputs/assignment"))) {
            return files.filter(p -> p.toString().endsWith(".xml")).sorted().toList();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    private Map<String, Mail> mails(int expected) throws Exception {
        HttpClient http = HttpClient.newHttpClient();
        URI api = URI.create("http://" + MAILHOG.getHost() + ":" + MAILHOG.getMappedPort(8025) + "/api/v2/messages?limit=250");
        JsonNode items = null;
        for (int i = 0; i < 50; i++) {
            items = new ObjectMapper().readTree(http.send(HttpRequest.newBuilder(api).build(), HttpResponse.BodyHandlers.ofString()).body()).get("items");
            if (items.size() >= expected) {
                break;
            }
            Thread.sleep(200);
        }
        Map<String, Mail> byClaim = new LinkedHashMap<>();
        for (JsonNode item : items) {
            List<String> envelope = new ArrayList<>();
            item.get("Raw").get("To").forEach(t -> envelope.add(t.asText()));
            MimeMessage mime = new MimeMessage(Session.getInstance(new Properties()),
                    new ByteArrayInputStream(item.get("Raw").get("Data").asText().getBytes(StandardCharsets.ISO_8859_1)));
            String text = null;
            byte[] notice = null;
            if (mime.getContent() instanceof Multipart parts) {
                for (int p = 0; p < parts.getCount(); p++) {
                    BodyPart part = parts.getBodyPart(p);
                    if (Part.ATTACHMENT.equalsIgnoreCase(part.getDisposition()) || part.getFileName() != null) {
                        notice = part.getInputStream().readAllBytes();
                    } else {
                        text = String.valueOf(part.getContent());
                    }
                }
            }
            Mail mail = new Mail(envelope, mime.getHeader("To", ","), mime.getSubject(), text, notice);
            byClaim.put(notice == null ? mime.getSubject() : between(new String(notice, StandardCharsets.UTF_8), "ClaimNumber"), mail);
        }
        return byClaim;
    }

    private static Mail mail(Run r, String requestId) {
        String claim = between(new String(r.requests().get(requestId), StandardCharsets.UTF_8), "ClaimNumber");
        Mail mail = r.mailByClaim().get(claim);
        if (mail == null || mail.notice() == null) {
            fail("no notice mailed with the AssignmentNotice attached for " + requestId + " (" + claim + ")");
        }
        return mail;
    }

    private static String notice(Run r, String requestId) {
        return new String(mail(r, requestId).notice(), StandardCharsets.UTF_8);
    }

    private static void event(Map<String, List<Event>> events, Exchange e, String what) {
        events.computeIfAbsent(id(e), k -> java.util.Collections.synchronizedList(new ArrayList<>())).add(new Event(what, System.nanoTime()));
    }

    private static String id(Exchange e) {
        return e.getProperty(REQUEST_ID, String.class);
    }

    private static long at(List<Event> events, String what, String id) {
        return events.stream().filter(e -> e.what().equals(what)).mapToLong(Event::at).findFirst()
                .orElseThrow(() -> new AssertionError(id + ": no " + what + " event"));
    }

    static String between(String xml, String element) {
        int from = xml.indexOf("<" + element + ">");
        int to = xml.indexOf("</" + element + ">");
        if (from < 0 || to < 0) {
            throw new AssertionError("no <" + element + "> in " + xml);
        }
        return xml.substring(from + element.length() + 2, to);
    }

    private static String stem(Path p) {
        String f = p.getFileName().toString();
        return f.substring(0, f.lastIndexOf('.'));
    }

    private static byte[] read(Path p) {
        try {
            return Files.readAllBytes(p);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String digest(byte[] bytes) {
        try {
            return bytes.length + " B, sha256 " + java.util.HexFormat.of().formatHex(
                    java.security.MessageDigest.getInstance("SHA-256").digest(bytes)).substring(0, 12);
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String firstLine(String s) {
        return s == null ? "" : s.lines().findFirst().orElse("");
    }
}
