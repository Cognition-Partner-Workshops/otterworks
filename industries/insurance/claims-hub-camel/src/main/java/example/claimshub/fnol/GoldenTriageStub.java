package example.claimshub.fnol;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Stands in for the ClaimTriage policy until the rules-table conversion is merged: answers with the outcome
 * and reasons the BizTalk Rule Engine gave for the claim, from {@code corpus/golden/triage/<ClaimNumber>.json}.
 * It keys on the claim number only; the facts are not evaluated.
 */
@Component
public class GoldenTriageStub implements ClaimTriage {

    private final Path goldenDir;
    private final ObjectMapper json = new ObjectMapper();

    public GoldenTriageStub(FnolIntakeProperties properties) {
        this.goldenDir = properties.triageGoldenDir();
    }

    @Override
    public TriageResult evaluate(String claimNumber, String triageFacts) {
        Path golden = goldenDir.resolve(claimNumber + ".json");
        if (!Files.isRegularFile(golden)) {
            throw new IllegalStateException("triage stub has no golden for " + claimNumber + " in " + goldenDir);
        }
        try {
            JsonNode node = json.readTree(golden.toFile());
            List<String> reasons = new ArrayList<>();
            node.path("Reasons").forEach(r -> reasons.add(r.asText()));
            return new TriageResult(node.path("Outcome").asText(), List.copyOf(reasons));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }
}
