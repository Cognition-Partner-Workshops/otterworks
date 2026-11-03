package com.otterworks.ottershops.order;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class OrderTrackingTest {
    static final UUID ID = UUID.fromString("00000000-0000-0000-0000-000000000042");
    static final Instant PLACED = Instant.parse("2026-11-27T18:00:00Z");

    @Test
    void freshShipOrderIsPlacedWithoutTracking() {
        OrderTracking t = OrderTracking.of(ID, "SHIP", "STANDARD", 0, PLACED, PLACED.plusSeconds(30));
        assertEquals("PLACED", t.currentStep());
        assertNull(t.trackingNumber());
        assertEquals(5, t.steps().size());
        assertEquals(PLACED.plus(Duration.ofDays(7)), t.estimatedArrival());
    }

    @Test
    void shippedOrderGetsStableTrackingNumber() {
        OrderTracking t = OrderTracking.of(ID, "SHIP", "EXPRESS", 0, PLACED, PLACED.plus(Duration.ofMinutes(11)));
        assertEquals("SHIPPED", t.currentStep());
        assertNotNull(t.trackingNumber());
        assertTrue(t.trackingNumber().matches("OP\\d{12}"));
        assertEquals(t.trackingNumber(), OrderTracking.of(ID, "SHIP", "EXPRESS", 0, PLACED, PLACED.plus(Duration.ofDays(1))).trackingNumber());
        assertEquals(PLACED.plus(Duration.ofDays(2)), t.estimatedArrival());
    }

    @Test
    void expressOrderIsDeliveredAfterTwoDays() {
        OrderTracking t = OrderTracking.of(ID, "SHIP", "EXPRESS", 0, PLACED, PLACED.plus(Duration.ofDays(3)));
        assertEquals("DELIVERED", t.currentStep());
        assertTrue(t.steps().stream().allMatch(OrderTracking.Step::done));
    }

    @Test
    void pickupIsReadyAfterStoreWindowAndNeverAutoCollected() {
        OrderTracking before = OrderTracking.of(ID, "PICKUP", null, 2, PLACED, PLACED.plus(Duration.ofHours(1)));
        assertEquals("PROCESSING", before.currentStep());
        OrderTracking after = OrderTracking.of(ID, "PICKUP", null, 2, PLACED, PLACED.plus(Duration.ofDays(5)));
        assertEquals("READY", after.currentStep());
        assertNull(after.carrier());
        assertEquals("PICKED_UP", after.steps().get(3).code());
    }
}
