package com.otterworks.ottershops.pricing;

/**
 * Display price for one product. {@code percentOff} is the saving against list price, rounded down
 * to a whole percent, for the badge.
 */
public record PriceInfo(int listCents, int priceCents, boolean onSale, boolean promoEligible, boolean excludedFromPromo, int percentOff) {}
