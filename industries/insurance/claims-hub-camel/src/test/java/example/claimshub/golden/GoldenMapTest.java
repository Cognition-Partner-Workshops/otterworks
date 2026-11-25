package example.claimshub.golden;

import static org.junit.jupiter.api.Assertions.fail;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.ProducerTemplate;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import example.claimshub.ClaimsHubApplication;
import example.claimshub.MapEndpoints;

/**
 * Golden-file test for one BizTalk map. A subclass names the map; this class sends every corpus input
 * listed for it in {@code corpus/manifest.yaml} to {@code direct:map.<MapName>} and compares the output
 * with {@code corpus/golden} byte for byte. One dynamic test per message; a message that does not match
 * stays red. Plain {@code @SpringBootTest} on purpose: Camel's test listener stops the context after the
 * factory method returns, before its dynamic tests run. The per-message table (message, byte-identical, cause) is written to
 * {@code target/golden-report/<MapName>.md} for the pull request body.
 */
@SpringBootTest(classes = ClaimsHubApplication.class, properties = {"camel.springboot.main-run-controller=false", "camel.component.direct.timeout=2000",
        "spring.flyway.enabled=false", "spring.datasource.url=jdbc:postgresql://localhost:5432/claimsledger"})
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
public abstract class GoldenMapTest {

    public record Row(String message, boolean identical, String cause) {
    }

    @Autowired
    protected CamelContext camelContext;

    @Autowired
    protected ProducerTemplate producer;

    private final List<Row> rows = new ArrayList<>();

    /** The map name exactly as in {@code corpus/manifest.yaml}, e.g. {@code CanonicalClaim_to_PolicyInqRq}. */
    protected abstract String mapName();

    /** The corpus this test runs over; defaults to the manifest entry for {@link #mapName()}. */
    protected CorpusManifest.MapSpec spec() {
        return CorpusManifest.load().map(mapName());
    }

    /**
     * Named causes for messages that cannot be made byte-identical, keyed by input file name. They do not
     * turn a red message green; they replace the generic first-difference text in the report and failure.
     */
    protected Map<String, String> knownCauses() {
        return Map.of();
    }

    /** Runs one source message through the map's Camel route and returns the target message bytes. */
    protected byte[] transform(Path input) throws Exception {
        Exchange result = producer.request(MapEndpoints.of(mapName()), exchange -> {
            exchange.getIn().setBody(Files.readAllBytes(input));
            exchange.getIn().setHeader(Exchange.FILE_NAME, input.getFileName().toString());
        });
        if (result.getException() != null) {
            throw new IllegalStateException("route failed for " + input.getFileName() + ": " + result.getException().getMessage(), result.getException());
        }
        Object body = result.getMessage().getBody();
        if (body instanceof String text) {
            return text.getBytes(StandardCharsets.UTF_8);
        }
        return result.getMessage().getMandatoryBody(byte[].class);
    }

    @TestFactory
    Stream<DynamicTest> corpus() {
        CorpusManifest.MapSpec spec = spec();
        if (camelContext.getRoute(MapEndpoints.routeId(mapName())) == null) {
            fail("no route " + MapEndpoints.routeId(mapName()) + " consuming " + MapEndpoints.of(mapName()));
        }
        List<Path> inputs = spec.inputFiles();
        if (inputs.isEmpty()) {
            fail("no corpus inputs under " + spec.inputs());
        }
        return inputs.stream().map(input -> DynamicTest.dynamicTest(input.getFileName().toString(), () -> check(spec, input)));
    }

    private void check(CorpusManifest.MapSpec spec, Path input) throws Exception {
        String message = input.getFileName().toString();
        Path golden = spec.goldenFor(input);
        if (!Files.exists(golden)) {
            record(new Row(message, false, "golden missing: " + golden.getFileName()));
            fail("golden missing for " + message);
        }
        ByteComparison comparison;
        try {
            comparison = ByteComparison.of(Files.readAllBytes(golden), transform(input));
        } catch (RuntimeException e) {
            record(new Row(message, false, "transform failed: " + e.getMessage()));
            throw e;
        }
        String cause = comparison.identical() ? "" : knownCauses().getOrDefault(message, comparison.cause());
        record(new Row(message, comparison.identical(), cause));
        if (!comparison.identical()) {
            fail(spec.name() + " " + message + ": " + cause);
        }
    }

    private synchronized void record(Row row) {
        rows.add(row);
    }

    protected List<Row> rows() {
        return List.copyOf(rows);
    }

    @AfterAll
    void writeReport() throws IOException {
        Path dir = Path.of("target", "golden-report");
        Files.createDirectories(dir);
        StringBuilder md = new StringBuilder();
        md.append("| Message | Byte-identical | Cause |\n| --- | --- | --- |\n");
        long identical = 0;
        for (Row row : rows) {
            md.append("| ").append(row.message()).append(" | ").append(row.identical() ? "yes" : "no")
                    .append(" | ").append(row.cause().isEmpty() ? "" : row.cause()).append(" |\n");
            if (row.identical()) {
                identical++;
            }
        }
        md.append("| **Total** | **").append(identical).append(" of ").append(rows.size())
                .append(" identical** | ").append(rows.size() - identical).append(" red |\n");
        Files.writeString(dir.resolve(spec().name() + ".md"), md.toString(), StandardCharsets.UTF_8);
    }
}
