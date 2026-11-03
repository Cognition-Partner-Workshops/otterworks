package com.otterworks.ottershops.order;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Post-purchase timeline. There is no warehouse behind the demo, so milestones advance on a fixed schedule from
 * the order time: processing after 2 minutes, shipped after 10, then the shipping method's transit days.
 * Pickup orders are ready after the store's pickup window and stay "ready" until collected.
 */
public record OrderTracking(String currentStep, String carrier, String trackingNumber, Instant estimatedArrival,
                            List<Step> steps) {

    public record Step(String code, String label, Instant at, boolean done) {}

    static final Duration PROCESSING = Duration.ofMinutes(2);
    static final Duration SHIPPED = Duration.ofMinutes(10);

    public static OrderTracking of(UUID orderId, String fulfillment, String shippingMethod, int readyInHours,
                                   Instant placed, Instant now) {
        List<Step> steps = new ArrayList<>();
        steps.add(new Step("PLACED", "Order placed", placed, true));
        steps.add(step("PROCESSING", "Processing", placed.plus(PROCESSING), now));
        if ("PICKUP".equals(fulfillment)) {
            Instant ready = placed.plus(Duration.ofHours(Math.max(0, readyInHours)));
            steps.add(step("READY", "Ready for pickup", ready, now));
            steps.add(new Step("PICKED_UP", "Picked up", null, false));
            return new OrderTracking(current(steps), null, null, ready, steps);
        }
        int days = "EXPRESS".equals(shippingMethod) ? 2 : 7;
        Instant delivered = placed.plus(Duration.ofDays(days));
        steps.add(step("SHIPPED", "Shipped", placed.plus(SHIPPED), now));
        steps.add(step("OUT_FOR_DELIVERY", "Out for delivery", delivered.minus(Duration.ofHours(8)), now));
        steps.add(step("DELIVERED", "Delivered", delivered, now));
        boolean shipped = !now.isBefore(placed.plus(SHIPPED));
        return new OrderTracking(current(steps), shipped ? "OtterPost" : null, shipped ? trackingNumber(orderId) : null,
                delivered, steps);
    }

    static Step step(String code, String label, Instant at, Instant now) {
        return new Step(code, label, at, !now.isBefore(at));
    }

    static String current(List<Step> steps) {
        String code = "PLACED";
        for (Step s : steps) if (s.done()) code = s.code();
        return code;
    }

    static String trackingNumber(UUID orderId) {
        long n = Math.abs(UUID.nameUUIDFromBytes(orderId.toString().getBytes(StandardCharsets.UTF_8)).getMostSignificantBits());
        return "OP" + String.format("%012d", n % 1_000_000_000_000L);
    }
}
