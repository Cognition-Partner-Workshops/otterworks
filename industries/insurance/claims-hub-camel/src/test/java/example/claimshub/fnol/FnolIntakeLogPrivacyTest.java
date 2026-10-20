package example.claimshub.fnol;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.camel.ProducerTemplate;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import example.claimshub.ClaimsHubApplication;

/**
 * The shipped completed, suspended and assignment URIs (application.yaml, which the Helm chart does not
 * override) must not write claimant PII to the application log. Every corpus FNOL runs through FnolIntake
 * with those defaults, and the captured stdout is searched for each insured's name and tax id.
 */
@SpringBootTest(classes = ClaimsHubApplication.class, properties = {
        "camel.springboot.main-run-controller=false",
        "camel.component.direct.timeout=2000",
        "claimshub.fnol.correction-window=4s"})
@ExtendWith(OutputCaptureExtension.class)
@DisplayName("FnolIntake default report URIs keep claimant PII out of the log")
class FnolIntakeLogPrivacyTest {

    private static final Pattern PII = Pattern.compile("<(GivenName|Surname|TaxId)>([^<]+)</\\1>");
    private static final Pattern COMPLETED_LINE = Pattern.compile("(?m)^.*\\bfnol\\.completed\\b.*$");

    @DynamicPropertySource
    static void legacySystems(DynamicPropertyRegistry registry) {
        var pg = LegacySystems.postgres();
        registry.add("spring.datasource.url", pg::getJdbcUrl);
        registry.add("spring.datasource.username", pg::getUsername);
        registry.add("spring.datasource.password", pg::getPassword);
        registry.add("claimshub.out-dir", () -> FnolIntakeTestBase.OUT.toString());
    }

    @Autowired
    private ProducerTemplate producer;

    @Test
    @DisplayName("16 FNOLs reported on the default log URIs, no GivenName, Surname or TaxId in the output")
    void defaultReportUrisDoNotLogClaimantPii(CapturedOutput output) throws Exception {
        LegacySystems.clearClaims();
        List<Path> inputs = FnolIntakeTestBase.fnolInputs();
        List<String> pii = new ArrayList<>();
        for (Path fnol : inputs) {
            String xml = FnolIntakeTestBase.read(fnol);
            Matcher m = PII.matcher(xml);
            while (m.find()) {
                pii.add(m.group(2));
            }
            producer.sendBody(FnolIntakeTestBase.FNOL_IN, xml);
        }
        assertThat(pii).as("PII values in the corpus FNOLs").hasSizeGreaterThanOrEqualTo(inputs.size() * 3);

        long deadline = System.nanoTime() + FnolIntakeTestBase.WINDOW.plusSeconds(60).toNanos();
        while (completedLines(output) < inputs.size() && System.nanoTime() < deadline) {
            Thread.sleep(Duration.ofMillis(250));
        }
        assertThat(completedLines(output)).as("fnol.completed log lines, one per instance").isEqualTo(inputs.size());

        String log = output.getAll();
        assertThat(pii).as("claimant PII written to the application log").noneMatch(log::contains);
        assertThat(log).as("InsertClaim ClaimantName in the application log").doesNotContain("ClaimantName");
    }

    private static long completedLines(CapturedOutput output) {
        return COMPLETED_LINE.matcher(output.getAll()).results().count();
    }
}
