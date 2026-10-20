package __PACKAGE__;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

/**
 * Copied into a claims-hub-camel checkout by claims-hub-dual-run/dual_run.py and never committed there.
 * Runs the rules table over every TriageFacts golden and writes each TriageResult to target/dual-run/triage
 * so the dual run can lay it out the way tools/triage_reference.py does and compare the bytes.
 */
class DualRunTriageCaptureTest {

    @Test
    void captureTriageResults() throws Exception {
        Path root = Path.of(System.getProperty("fixture.dir", "../biztalk-claims-intake"));
        Path out = Path.of("target", "dual-run", "triage");
        Files.createDirectories(out);
        TriageEvaluator evaluator = new TriageEvaluator(RulesTable.load(new ClassPathResource("rules/claim-triage.csv")));
        ObjectMapper json = new ObjectMapper();
        List<Path> facts;
        try (Stream<Path> files = Files.list(root.resolve("corpus/golden/triage-facts"))) {
            facts = files.filter(p -> p.toString().endsWith(".xml")).sorted().toList();
        }
        for (Path file : facts) {
            TriageResult result = evaluator.evaluate(TriageFactsReader.read(Files.readString(file)));
            ObjectNode node = json.createObjectNode();
            node.put("ClaimNumber", result.claimNumber());
            node.put("Outcome", result.outcome());
            node.set("Reasons", json.valueToTree(result.reasons()));
            node.set("RulesFired", json.valueToTree(result.rulesFired()));
            Files.writeString(out.resolve(file.getFileName().toString().replace(".xml", ".json")), json.writeValueAsString(node));
        }
    }
}
