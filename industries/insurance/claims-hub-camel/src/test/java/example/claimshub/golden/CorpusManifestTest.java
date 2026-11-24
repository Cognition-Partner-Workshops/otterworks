package example.claimshub.golden;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.util.List;

import org.junit.jupiter.api.Test;

class CorpusManifestTest {

    private final CorpusManifest manifest = CorpusManifest.load();

    @Test
    void readsEveryMapOfTheHub() {
        assertThat(manifest.maps()).extracting(CorpusManifest.MapSpec::name).containsExactly(
                "Fnol_to_CanonicalClaim",
                "CanonicalClaim_to_PolicyInqRq",
                "Claim_PolicyInqRs_to_InsertClaim",
                "InsertClaim_to_TriageFacts",
                "Payment_to_VendorRemittance",
                "Payment_to_LedgerPost",
                "AssignmentRequest_to_RosterQuery",
                "Roster_AssignmentRequest_to_Notice");
    }

    @Test
    void everyInputHasAGolden() {
        int total = 0;
        for (CorpusManifest.MapSpec spec : manifest.maps()) {
            List<java.nio.file.Path> inputs = spec.inputFiles();
            assertThat(inputs).as(spec.name()).isNotEmpty();
            for (var input : inputs) {
                assertThat(Files.exists(spec.goldenFor(input))).as(spec.name() + " " + input.getFileName()).isTrue();
            }
            total += inputs.size();
        }
        assertThat(total).as("map outputs in the corpus").isEqualTo(112);
    }
}
