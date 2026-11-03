package com.otterworks.ottershops.order;

import com.otterworks.ottershops.common.ApiException;
import com.otterworks.ottershops.ops.OpsAuth;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Store-associate actions on an order (called by the store app with the ops key). */
@RestController
@RequestMapping("/api/ops/orders")
public class OrderStatusController {
    private final JdbcTemplate jdbc;
    private final OpsAuth auth;

    public OrderStatusController(JdbcTemplate jdbc, OpsAuth auth) {
        this.jdbc = jdbc;
        this.auth = auth;
    }

    @PostMapping("/{number}/picked-up")
    public Map<String, String> pickedUp(@RequestHeader(value = "X-Ops-Key", required = false) String key,
                                        @PathVariable String number) {
        auth.check(key);
        String status = jdbc.queryForList("SELECT status FROM orders WHERE order_number = ? AND fulfillment = 'PICKUP'",
                String.class, number).stream().findFirst().orElseThrow(() -> ApiException.notFound("Order"));
        if (!"READY_FOR_PICKUP".equals(status)) {
            throw new ApiException(HttpStatus.CONFLICT, "ORDER_NOT_READY", "Order " + number + " is " + status + ", not ready for pickup");
        }
        jdbc.update("UPDATE orders SET status = 'PICKED_UP', updated_at = now() WHERE order_number = ?", number);
        return Map.of("orderNumber", number, "status", "PICKED_UP");
    }
}
