package example.claimshub.fnol;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.stream.Stream;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.component.mock.MockEndpoint;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import example.claimshub.ClaimsHubApplication;
import example.claimshub.golden.CorpusManifest;

/**
 * Drives FnolIntake the way BizTalk does: one ACORD FNOL per message onto {@code direct:fnol.in} (what the
 * receive pipeline hands the MessageBox), the WCF-SQL ports on the PostgreSQL stand-in, and every
 * outbound port observable. The correction window is shortened to {@link #WINDOW} so the delay branch can
 * be exercised; the 15 minute production value is pinned separately.
 *
 * Contract the route is held to, all named after the XLANG/s:
 * - {@code mock:fnol.completed} gets one exchange per orchestration instance, header {@code FnolStatus}
 *   {@code COMPLETED} or {@code TERMINATED}, with the orchestration's messages as exchange properties
 *   {@code msgClaim}, {@code msgPolicyRq}, {@code msgPolicyRs}, {@code msgInsertClaim} (map output) and
 *   {@code msgTriageFacts} (before the policy runs), and {@code triageOutcome}.
 * - {@code mock:fnol.suspended} gets an instance that failed, header {@code FnolSuspendedReason}.
 * - {@code mock:fnol.rejected} gets a correction refused because it came from another agency than the
 *   original FNOL, headers {@code AgencyId} (the sender) and {@code OriginalAgencyId}.
 * - {@code mock:fnol.assignment} gets the usp_InsertClaim of every claim sent on to adjuster assignment.
 * - Fraud referrals, declines and glass fast tracks are written as files, laid out like the binding's
 *   FILE and SFTP addresses, under {@link #OUT}.
 */
@SpringBootTest(classes = ClaimsHubApplication.class, properties = {
        "camel.springboot.main-run-controller=false",
        "camel.component.direct.timeout=2000",
        "claimshub.fnol.correction-window=4s",
        "claimshub.fnol.completed-uri=mock:fnol.completed",
        "claimshub.fnol.suspended-uri=mock:fnol.suspended",
        "claimshub.fnol.assignment-uri=mock:fnol.assignment",
        "claimshub.fnol.rejected-uri=mock:fnol.rejected"})
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
abstract class FnolIntakeTestBase {

    static final String FNOL_IN = "direct:fnol.in";
    static final Duration WINDOW = Duration.ofSeconds(4);
    static final Path OUT;

    static {
        try {
            OUT = Files.createTempDirectory("fnol-out");
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    @DynamicPropertySource
    static void legacySystems(DynamicPropertyRegistry registry) {
        var pg = LegacySystems.postgres();
        registry.add("spring.datasource.url", pg::getJdbcUrl);
        registry.add("spring.datasource.username", pg::getUsername);
        registry.add("spring.datasource.password", pg::getPassword);
        registry.add("claimshub.out-dir", OUT::toString);
    }

    @Autowired
    protected CamelContext camelContext;

    @Autowired
    protected ProducerTemplate producer;

    protected MockEndpoint completed() {
        return camelContext.getEndpoint("mock:fnol.completed", MockEndpoint.class);
    }

    protected MockEndpoint suspended() {
        return camelContext.getEndpoint("mock:fnol.suspended", MockEndpoint.class);
    }

    protected MockEndpoint rejected() {
        return camelContext.getEndpoint("mock:fnol.rejected", MockEndpoint.class);
    }

    protected MockEndpoint assignment() {
        return camelContext.getEndpoint("mock:fnol.assignment", MockEndpoint.class);
    }

    protected void reset() throws IOException {
        MockEndpoint.resetMocks(camelContext);
        LegacySystems.clearClaims();
        if (Files.exists(OUT)) {
            try (Stream<Path> walk = Files.walk(OUT)) {
                walk.sorted(java.util.Comparator.reverseOrder()).filter(p -> !p.equals(OUT)).forEach(p -> p.toFile().delete());
            }
        }
    }

    protected void send(String fnol) {
        producer.sendBody(FNOL_IN, fnol);
    }

    static Path fixture(String relative) {
        return CorpusManifest.fixtureDir().resolve(relative);
    }

    static String read(Path path) {
        try {
            return Files.readString(path, StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new java.io.UncheckedIOException(e);
        }
    }

    static List<Path> fnolInputs() {
        try (Stream<Path> files = Files.list(fixture("corpus/inputs/fnol"))) {
            return files.filter(p -> p.toString().endsWith(".xml")).sorted().toList();
        } catch (IOException e) {
            throw new java.io.UncheckedIOException(e);
        }
    }

    static List<String> outFiles(String relativeDir) {
        Path dir = OUT.resolve(relativeDir);
        if (!Files.isDirectory(dir)) {
            return List.of();
        }
        try (Stream<Path> walk = Files.walk(dir)) {
            return walk.filter(Files::isRegularFile).map(p -> dir.relativize(p).toString()).sorted().toList();
        } catch (IOException e) {
            throw new java.io.UncheckedIOException(e);
        }
    }

    static String claimNumber(Exchange exchange) {
        return exchange.getMessage().getHeader("ClaimNumber", String.class);
    }
}
