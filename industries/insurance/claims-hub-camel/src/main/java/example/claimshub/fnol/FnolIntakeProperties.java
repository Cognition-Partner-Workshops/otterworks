package example.claimshub.fnol;

import java.nio.file.Path;
import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Settings for the FnolIntake route.
 *
 * @param correctionWindow the Delay_CorrectionWindow shape: how long an instance waits for a corrected FNOL
 * @param fixtureDir the BizTalk solution; the maps run from its {@code Maps/}
 * @param outDir root the FILE and SFTP subscriptions write under, laid out like the binding's addresses
 * @param completedUri where a finished instance is reported (COMPLETED or TERMINATED)
 * @param suspendedUri where an instance that failed is reported, BizTalk's suspended queue
 * @param assignmentUri Assignment.RequestAssignment, until AdjusterAssignment is converted
 */
@ConfigurationProperties("claimshub.fnol")
public record FnolIntakeProperties(Duration correctionWindow, String fixtureDir, String outDir, String completedUri,
        String suspendedUri, String assignmentUri) {

    public Path fixturePath() {
        return Path.of(fixtureDir).toAbsolutePath().normalize();
    }

    public Path outPath() {
        return Path.of(outDir).toAbsolutePath().normalize();
    }

    public Path mapsDir() {
        return fixturePath().resolve("Maps");
    }
}
