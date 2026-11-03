package com.otterworks.ottershops.pricing;

import java.util.Map;

public record CodeDiscount(PromoCode code, int totalCents, Map<String, Integer> perLine) {}
