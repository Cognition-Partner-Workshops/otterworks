package example.claimshub.payment;

import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** The vendor SFTP server is up; the service window is not enforced so the tests do not wait for 22:00. */
abstract class ReachableVendorTestSupport extends ClaimPaymentTestSupport {

    @DynamicPropertySource
    static void reachableVendor(DynamicPropertyRegistry registry) {
        hubProperties(registry, true);
    }
}
