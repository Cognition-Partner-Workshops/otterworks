package example.claimshub.payment;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;
import java.util.stream.Stream;

import org.apache.camel.Exchange;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;

/**
 * The 14 corpus remittance files handed to Vendor.DeliverRemittance as they are. The legacy send pipeline
 * (TrailerTotalsComponent, re-implemented in {@link TrailerTotalsReference} as the oracle) sends the ones
 * whose trailer it can read and agree with, and suspends the rest before the SFTP adapter sees them. The
 * route must do the same: a file the oracle accepts arrives byte-identical, a file it refuses is never sent.
 */
class TrailerGuardCorpusTest extends ReachableVendorTestSupport {

    @TestFactory
    Stream<DynamicTest> corpusFilesThroughTheGuard() throws Exception {
        List<String> ids = instructionIds();
        return ids.stream().map(id -> DynamicTest.dynamicTest(id, () -> deliver(id)));
    }

    private void deliver(String id) throws Exception {
        recorder.reset();
        clearVendorInbox();
        byte[] golden = Files.readAllBytes(remittanceGolden(id));
        String verdict = TrailerTotalsReference.legacyVerdict(new String(golden, StandardCharsets.US_ASCII));

        Exchange result = producer.request("direct:vendor.deliver", exchange -> {
            exchange.getIn().setBody(golden);
            exchange.getIn().setHeader(Exchange.FILE_NAME, id + ".xml");
        });

        if (verdict == null) {
            assertThat(result.getException()).isNull();
            List<String> files = vendorFilesFor(id);
            assertThat(files).hasSize(1);
            assertThat(vendorFile(files.get(0))).isEqualTo(golden);
        } else {
            assertThat(result.getException()).as("legacy pipeline suspends: %s", verdict).isNotNull();
            assertThat(result.getException()).as("refused by the trailer guard, not by anything else").hasStackTraceContaining("TrailerTotals");
            assertThat(recorder.sftpSends()).isEmpty();
            assertThat(vendorFiles()).isEmpty();
        }
    }
}
