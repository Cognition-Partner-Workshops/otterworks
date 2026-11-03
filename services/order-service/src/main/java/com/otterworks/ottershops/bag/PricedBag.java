package com.otterworks.ottershops.bag;

import java.util.List;

/** A bag priced by the server: the only prices checkout trusts. */
public record PricedBag(List<Line> lines, int listSubtotalCents, int subtotalCents, int discountCents,
                        String promoCode, String promoDescription, String promoError) {

    public record Line(String sku, String productId, String name, String color, String size, String image,
                       int quantity, int stock, int unitListCents, int unitPriceCents, int lineSubtotalCents,
                       int discountCents, int lineTotalCents, boolean promoEligible, boolean excludedFromPromo) {}

    public int itemCount() {
        return lines.stream().mapToInt(Line::quantity).sum();
    }

    public int merchandiseCents() {
        return subtotalCents - discountCents;
    }
}
