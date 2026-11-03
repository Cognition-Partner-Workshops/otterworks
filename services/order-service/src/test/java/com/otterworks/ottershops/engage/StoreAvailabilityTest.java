package com.otterworks.ottershops.engage;

import com.otterworks.ottershops.catalog.Sku;
import com.otterworks.ottershops.catalog.Store;
import org.junit.jupiter.api.Test;

import java.util.stream.IntStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class StoreAvailabilityTest {
    static Sku sku(int stock) {
        return new Sku("P1-NVY-M", "P1", "Navy", "#000", "blue", "M", 3, stock);
    }

    static Store store(String id, boolean pickup) {
        return new Store(id, "Store " + id, "1 Main", "Austin", "TX", "78701", "555", "10-9", null, null, pickup, 2);
    }

    @Test
    void soldOutOnlineMeansUnavailableEverywhere() {
        StoreAvailability.Result r = StoreAvailability.of(sku(0), store("S1", true));
        assertEquals(StoreAvailability.Level.UNAVAILABLE, r.level());
        assertFalse(r.canPickUp());
    }

    @Test
    void storeQuantityIsStableAndNeverExceedsNetworkStock() {
        IntStream.range(0, 40).forEach(i -> {
            Store s = store("S" + i, true);
            int q = StoreAvailability.quantity(sku(2), s);
            assertTrue(q >= 0 && q <= 2);
            assertEquals(q, StoreAvailability.quantity(sku(2), s));
        });
    }

    @Test
    void someStoresCarryAndSomeDoNot() {
        long carrying = IntStream.range(0, 40).filter(i -> StoreAvailability.quantity(sku(50), store("S" + i, true)) > 0).count();
        assertTrue(carrying > 10 && carrying < 40);
    }

    @Test
    void pickupDisabledStoreCannotPickUp() {
        for (int i = 0; i < 20; i++) {
            StoreAvailability.Result r = StoreAvailability.of(sku(50), store("S" + i, false));
            assertFalse(r.canPickUp());
        }
    }
}
