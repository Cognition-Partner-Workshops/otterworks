package com.otterworks.insurance.claimshub.triage;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

/**
 * Runs the rules table over the 16 TriageFacts goldens and compares every claim with what
 * tools/triage_reference.py wrote for it (corpus/golden/triage, kept current by
 * {@code triage_reference.py check}). Writes the side-by-side report to target/parity.
 */
class TriageParityTest {

    private static final ObjectMapper JSON = new ObjectMapper();

    record Row(String claim, List<String> firedOld, List<String> firedNew, String outcomeOld, String outcomeNew,
               List<String> reasonsOld, List<String> reasonsNew) {

        List<String> differences() {
            List<String> d = new ArrayList<>();
            if (!firedOld.equals(firedNew)) {
                d.add("rules fired");
            }
            if (!outcomeOld.equals(outcomeNew)) {
                d.add("outcome");
            }
            if (!reasonsOld.equals(reasonsNew)) {
                d.add("reasons");
            }
            return d;
        }
    }

    @Test
    void rulesTableMatchesTheReferenceOnEveryGolden() throws IOException {
        TriageEvaluator evaluator = new TriageEvaluator(RulesTable.load(new ClassPathResource(Fixture.TABLE)));
        List<Path> facts;
        try (Stream<Path> files = Files.list(Fixture.FACTS)) {
            facts = files.filter(p -> p.toString().endsWith(".xml")).sorted().toList();
        }
        List<Row> rows = new ArrayList<>();
        for (Path file : facts) {
            TriageResult actual = evaluator.evaluate(TriageFactsReader.read(Files.readString(file)));
            String claim = file.getFileName().toString().replace(".xml", "");
            JsonNode expected = JSON.readTree(Fixture.REFERENCE_RESULTS.resolve(claim + ".json").toFile());
            assertThat(actual.claimNumber()).isEqualTo(expected.get("ClaimNumber").asText());
            rows.add(new Row(claim, strings(expected.get("RulesFired")), actual.rulesFired(),
                    expected.get("Outcome").asText(), actual.outcome(),
                    strings(expected.get("Reasons")), actual.reasons()));
        }
        writeReport(rows);

        assertThat(rows).hasSize(16);
        assertThat(rows).allSatisfy(r -> assertThat(r.differences()).as(r.claim()).isEmpty());
    }

    private static List<String> strings(JsonNode array) {
        List<String> out = new ArrayList<>();
        array.forEach(n -> out.add(n.asText()));
        return out;
    }

    private static void writeReport(List<Row> rows) throws IOException {
        StringBuilder md = new StringBuilder();
        md.append("| Claim | Rules fired (BRE reference) | Rules fired (rules table) | Outcome (BRE reference) "
                + "| Outcome (rules table) | Reasons (BRE reference) | Reasons (rules table) | Difference | Verdict |\n");
        md.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n");
        Map<String, int[]> outcomes = new TreeMap<>();
        int matched = 0;
        for (Row r : rows) {
            List<String> diff = r.differences();
            boolean match = diff.isEmpty();
            matched += match ? 1 : 0;
            outcomes.computeIfAbsent(r.outcomeOld(), k -> new int[2])[0]++;
            outcomes.computeIfAbsent(r.outcomeNew(), k -> new int[2])[1]++;
            md.append("| ").append(r.claim())
                    .append(" | ").append(String.join(", ", r.firedOld()))
                    .append(" | ").append(String.join(", ", r.firedNew()))
                    .append(" | ").append(r.outcomeOld())
                    .append(" | ").append(r.outcomeNew())
                    .append(" | ").append(String.join("<br>", r.reasonsOld()))
                    .append(" | ").append(String.join("<br>", r.reasonsNew()))
                    .append(" | ").append(match ? "none" : String.join(", ", diff) + " differ")
                    .append(" | ").append(match ? "MATCH" : "DIFFERS")
                    .append(" |\n");
        }
        md.append("| **Total** | | | | | | | ").append(rows.size() - matched).append(" claims differ | ")
                .append(matched).append(" of ").append(rows.size()).append(" match |\n\n");
        md.append("| Outcome | BRE reference | Rules table | Difference |\n| --- | --- | --- | --- |\n");
        int totalOld = 0;
        int totalNew = 0;
        for (Map.Entry<String, int[]> e : outcomes.entrySet()) {
            int[] c = e.getValue();
            totalOld += c[0];
            totalNew += c[1];
            md.append("| ").append(e.getKey()).append(" | ").append(c[0]).append(" | ").append(c[1])
                    .append(" | ").append(c[1] - c[0]).append(" |\n");
        }
        md.append("| **Total** | ").append(totalOld).append(" | ").append(totalNew).append(" | ")
                .append(totalNew - totalOld).append(" |\n");
        Path report = Path.of(System.getProperty("parity.report", "target/parity/triage-parity.md"));
        Files.createDirectories(report.getParent());
        Files.writeString(report, md.toString(), StandardCharsets.UTF_8);
    }
}
