package com.otterworks.ottershops.engage;

import com.otterworks.ottershops.catalog.Sku;
import com.otterworks.ottershops.catalog.Store;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Store-level stock for buy-online-pick-up-in-store. The core schema only tracks network stock per SKU, so each
 * store's shelf count is a stable share of it derived from the SKU and store ids: the same answer on every call.
 */
public final class StoreAvailability {
    private StoreAvailability() {}

    public enum Level { IN_STOCK, LIMITED, UNAVAILABLE }

    public record Result(String storeId, String storeName, String address, String city, String state, String zip,
                         String phone, String hours, boolean pickupEnabled, int readyInHours, int quantity, Level level,
                         boolean canPickUp) {}

    static int bucket(String sku, String storeId) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest((sku + "@" + storeId).getBytes(StandardCharsets.UTF_8));
            return Byte.toUnsignedInt(d[0]) % 10;
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    public static int quantity(Sku sku, Store store) {
        if (sku.stock() == 0) return 0;
        int b = bucket(sku.sku(), store.id());
        if (b < 2) return 0;
        return Math.min(sku.stock(), b < 5 ? 1 + b % 2 : 3 + b % 5);
    }

    public static Result of(Sku sku, Store store) {
        int qty = quantity(sku, store);
        Level level = qty == 0 ? Level.UNAVAILABLE : qty <= 2 ? Level.LIMITED : Level.IN_STOCK;
        return new Result(store.id(), store.name(), store.address(), store.city(), store.state(), store.zip(),
                store.phone(), store.hours(), store.pickupEnabled(), store.pickupReadyHours(), qty, level,
                store.pickupEnabled() && qty > 0);
    }
}
