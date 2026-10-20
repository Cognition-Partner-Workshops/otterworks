package example.claimshub.payment;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

import org.apache.camel.Exchange;
import org.junit.jupiter.api.Test;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * The vendor send port has a service window (22:00 to 05:30 in the binding): outside it BizTalk holds the
 * message and the attempt is made when the window opens. Here the window opens twenty seconds after the
 * context is configured, so the first attempt has to wait for it.
 */
class ClaimPaymentVendorWindowTest extends ClaimPaymentTestSupport {

    static LocalTime OPENS;

    @DynamicPropertySource
    static void windowOpensSoon(DynamicPropertyRegistry registry) {
        OPENS = LocalTime.now(ZoneOffset.UTC).plusSeconds(20);
        hubProperties(registry, true);
        DateTimeFormatter hms = DateTimeFormatter.ofPattern("HH:mm:ss");
        registry.add("claims.payment.vendor.window.enabled", () -> "true");
        registry.add("claims.payment.vendor.window.zone", () -> "UTC");
        registry.add("claims.payment.vendor.window.from", () -> OPENS.format(hms));
        registry.add("claims.payment.vendor.window.to", () -> OPENS.plusHours(1).format(hms));
    }

    @Test
    void theFirstAttemptWaitsForTheVendorWindowToOpen() throws Exception {
        Exchange result = pay("PI-2026-880106");

        assertThat(result.getException()).isNull();
        assertThat(recorder.sftpSends()).hasSize(1);
        assertThat(LocalTime.now(ZoneOffset.UTC)).isAfterOrEqualTo(OPENS.withNano(0));
        assertThat(vendorFilesFor("PI-2026-880106")).hasSize(1);
    }
}
