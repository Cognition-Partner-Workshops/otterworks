package com.otterworks.ottershops.pricing;

import com.otterworks.ottershops.common.ApiException;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PricingServiceTest {
    static final Promotion BF = new Promotion(true, "bf", "Black Friday", "h", "s", "b",
            Instant.parse("2026-11-01T00:00:00Z"), Instant.parse("2026-12-01T07:59:59Z"), 40,
            List.of("maternity", "essentials-forever"),
            List.of(new PromoCode("BLACKFRIDAY", "Extra 15%", 15, 0, false),
                    new PromoCode("OTTERWELCOME", "10% off $75+", 10, 7500, true)));

    static PricingService at(String instant, Promotion p) {
        return new PricingService(p, Clock.fixed(Instant.parse(instant), ZoneOffset.UTC));
    }

    @Test
    void promotionPriceBeatsMarkdownWhenLower() {
        PriceInfo p = at("2026-11-27T12:00:00Z", BF).price(5999, 4999, List.of("women"));
        assertEquals(3599, p.priceCents());
        assertTrue(p.onSale());
        assertEquals(40, p.percentOff());
    }

    @Test
    void excludedCollectionsStayFullPrice() {
        PriceInfo p = at("2026-11-27T12:00:00Z", BF).price(2499, null, List.of("women", "essentials-forever"));
        assertEquals(2499, p.priceCents());
        assertFalse(p.onSale());
        assertTrue(p.excludedFromPromo());
    }

    @Test
    void promotionOffOutsideWindowAndWhenDisabled() {
        assertEquals(5999, at("2026-12-02T00:00:00Z", BF).price(5999, null, List.of("women")).priceCents());
        assertEquals(5999, at("2026-11-27T12:00:00Z", BF.withEnabled(false)).price(5999, null, List.of("women")).priceCents());
    }

    @Test
    void codeDiscountSplitsAcrossEligibleLinesAndSumsExactly() {
        CodeDiscount d = at("2026-11-27T12:00:00Z", BF).applyCode("blackfriday",
                List.of(new PricedLine("a", 3333, true), new PricedLine("b", 3334, true), new PricedLine("c", 2499, false)));
        assertEquals(Math.round(6667 * 0.15), d.totalCents());
        assertEquals(d.totalCents(), d.perLine().values().stream().mapToInt(Integer::intValue).sum());
        assertEquals(0, d.perLine().get("c"));
    }

    @Test
    void unknownAndBelowMinimumCodesFailClearly() {
        PricingService s = at("2026-11-27T12:00:00Z", BF);
        ApiException unknown = assertThrows(ApiException.class, () -> s.applyCode("NOPE", List.of(new PricedLine("a", 1000, true))));
        assertEquals("PROMO_INVALID", unknown.error());
        ApiException min = assertThrows(ApiException.class, () -> s.applyCode("OTTERWELCOME", List.of(new PricedLine("a", 5000, true))));
        assertEquals("PROMO_MINIMUM_NOT_MET", min.error());
        assertTrue(min.getMessage().contains("$25.00"));
    }

    @Test
    void codeOnlyForExcludedItemsIsNotApplicable() {
        ApiException e = assertThrows(ApiException.class, () -> at("2026-11-27T12:00:00Z", BF)
                .applyCode("BLACKFRIDAY", List.of(new PricedLine("a", 2499, false))));
        assertEquals("PROMO_NOT_APPLICABLE", e.error());
    }
}
