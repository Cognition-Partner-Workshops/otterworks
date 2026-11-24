package example.claimshub.payment;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.InputStream;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

/** The production values of the ClaimPayment ports, as Bindings/ClaimsHub.BindingInfo.xml and ClaimPayment.odx set them. */
class ClaimPaymentConfigurationTest {

    @SuppressWarnings("unchecked")
    private static Object at(Map<String, Object> doc, String path) {
        Object node = doc;
        for (String key : path.split("\\.")) {
            if (!(node instanceof Map)) {
                return null;
            }
            node = ((Map<String, Object>) node).get(key);
        }
        return node;
    }

    @Test
    void portsCarryTheBindingValues() throws Exception {
        Map<String, Object> doc;
        try (InputStream in = getClass().getResourceAsStream("/application.yaml")) {
            doc = new Yaml().load(in);
        }
        assertThat(at(doc, "claims.payment.vendor.attempts")).as("Loop_Deliver: attempts < 3").isEqualTo(3);
        assertThat(String.valueOf(at(doc, "claims.payment.vendor.retry-delay"))).as("delay new TimeSpan(0, 10, 0)").isEqualTo("10m");
        assertThat(at(doc, "claims.payment.vendor.window.enabled")).isEqualTo(true);
        assertThat(String.valueOf(at(doc, "claims.payment.vendor.window.from"))).isEqualTo("22:00");
        assertThat(String.valueOf(at(doc, "claims.payment.vendor.window.to"))).isEqualTo("05:30");
        assertThat(at(doc, "claims.payment.vendor.username")).isEqualTo("thistlecombe-remit");
        assertThat(at(doc, "claims.payment.vendor.directory")).isEqualTo("inbound/thistlecombe");
        assertThat(at(doc, "claims.payment.vendor.temporary-folder")).isEqualTo("tmp");
        assertThat(at(doc, "claims.ops.to")).isEqualTo("claims-payments-ops@thistlecombe.example");
        assertThat(at(doc, "claims.ops.from")).isEqualTo("claims-hub@thistlecombe.example");
    }
}
