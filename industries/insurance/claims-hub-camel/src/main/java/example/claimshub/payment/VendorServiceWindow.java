package example.claimshub.payment;

import java.time.Duration;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * The ServiceWindow of sp_PaymentVendor_Remittance_SFTP: outside it the send port holds the message, so an
 * attempt waits for the window to open. A window whose end is before its start runs over midnight.
 */
@Component
public class VendorServiceWindow {

    private final boolean enabled;
    private final LocalTime from;
    private final LocalTime to;
    private final ZoneId zone;

    public VendorServiceWindow(@Value("${claims.payment.vendor.window.enabled}") boolean enabled,
            @Value("${claims.payment.vendor.window.from}") String from,
            @Value("${claims.payment.vendor.window.to}") String to,
            @Value("${claims.payment.vendor.window.zone}") String zone) {
        this.enabled = enabled;
        this.from = LocalTime.parse(from);
        this.to = LocalTime.parse(to);
        this.zone = ZoneId.of(zone);
    }

    public boolean isOpen(LocalTime time) {
        if (!enabled) {
            return true;
        }
        return from.isBefore(to)
                ? !time.isBefore(from) && time.isBefore(to)
                : !time.isBefore(from) || time.isBefore(to);
    }

    public Duration untilOpen(ZonedDateTime now) {
        if (isOpen(now.toLocalTime())) {
            return Duration.ZERO;
        }
        ZonedDateTime opens = now.with(from);
        if (!opens.isAfter(now)) {
            opens = opens.plusDays(1);
        }
        return Duration.between(now, opens);
    }

    public void awaitOpen() throws InterruptedException {
        Duration wait;
        while (!(wait = untilOpen(ZonedDateTime.now(zone))).isZero()) {
            Thread.sleep(Math.max(1, Math.min(wait.toMillis(), 60_000)));
        }
    }
}
