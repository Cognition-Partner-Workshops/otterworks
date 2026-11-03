package com.otterworks.ottershops.pricing;

public record PromoCode(String code, String description, int percentOff, int minSubtotalCents, boolean appliesToExcluded) {}
