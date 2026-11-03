package com.otterworks.ottershops.order;

import com.otterworks.ottershops.pricing.Fee;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record OrderView(UUID id, String orderNumber, String invoiceNumber, String email, String status,
                        String fulfillment, String shippingMethod, Pickup pickup, Address shipTo, String phone,
                        String promoCode, List<Line> lines, int subtotalCents, int discountCents, int shippingCents,
                        List<Fee> fees, int feesCents, BigDecimal taxRate, int taxCents, int totalCents,
                        String cardBrand, String cardLast4, int pointsEarned, Instant createdAt) {

    public record Line(int lineNo, String sku, String productId, String name, String color, String size, String image,
                       int quantity, int unitListCents, int unitPriceCents, int discountCents, int lineTotalCents) {}

    public record Address(String name, String line1, String line2, String city, String state, String zip) {}

    public record Pickup(String storeId, String storeName, String address, String city, String state, String zip,
                         int readyInHours) {}

    public record Summary(String orderNumber, String status, String fulfillment, int itemCount, int totalCents,
                          Instant createdAt, String image) {}
}
