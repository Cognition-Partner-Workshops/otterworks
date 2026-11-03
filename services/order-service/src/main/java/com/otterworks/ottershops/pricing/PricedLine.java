package com.otterworks.ottershops.pricing;

/** A bag or order line as the promo-code engine sees it. {@code lineTotalCents} is unit price x quantity. */
public record PricedLine(String key, long lineTotalCents, boolean eligible) {}
