package com.otterworks.ottershops.pricing;

import com.otterworks.ottershops.common.ApiException;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** QA gap coverage: promo codes, exclusions and the PROMO_ENABLED kill switch. */
class PricingQaTest {
    static final String BLACK_FRIDAY = "2026-11-27T12:00:00Z";

    static PricingService svc(boolean enabled) {
        return PricingServiceTest.at(BLACK_FRIDAY, PricingServiceTest.BF.withEnabled(enabled));
    }

    @Test
    void unknownCodeIsRejected() {
        ApiException e = assertThrows(ApiException.class,
                () -> svc(true).applyCode("NOPE", List.of(new PricedLine("a", 5000, true))));
        assertTrue(e.getMessage().contains("NOPE"));
    }

    @Test
    void belowMinimumReportsShortfall() {
        ApiException e = assertThrows(ApiException.class,
                () -> svc(true).applyCode("OTTERWELCOME", List.of(new PricedLine("a", 7499, true))));
        assertEquals("Add $0.01 more to use OTTERWELCOME", e.getMessage());
    }

    @Test
    void codeIsCaseAndWhitespaceInsensitive() {
        CodeDiscount d = svc(true).applyCode("  blackFriday ", List.of(new PricedLine("a", 1000, true)));
        assertEquals(150, d.totalCents());
    }

    @Test
    void blackFridayCodeSkipsExcludedLinesButWelcomeCodeDoesNot() {
        List<PricedLine> lines = List.of(new PricedLine("sale", 6000, true), new PricedLine("essentials", 4000, false));
        CodeDiscount bf = svc(true).applyCode("BLACKFRIDAY", lines);
        assertEquals(900, bf.totalCents());
        assertEquals(0, bf.perLine().get("essentials"));
        CodeDiscount welcome = svc(true).applyCode("OTTERWELCOME", lines);
        assertEquals(1000, welcome.totalCents());
        assertEquals(400, welcome.perLine().get("essentials"));
    }

    @Test
    void blackFridayOnOnlyExcludedItemsIsNotApplicable() {
        assertThrows(ApiException.class,
                () -> svc(true).applyCode("BLACKFRIDAY", List.of(new PricedLine("m", 4000, false))));
    }

    @Test
    void splitAlwaysSumsToTotal() {
        List<PricedLine> lines = List.of(new PricedLine("a", 333, true), new PricedLine("b", 333, true), new PricedLine("c", 334, true));
        CodeDiscount d = svc(true).applyCode("BLACKFRIDAY", lines);
        assertEquals(d.totalCents(), d.perLine().values().stream().mapToInt(Integer::intValue).sum());
    }

    @Test
    void promoDisabledMeansListPricesAndNoCodes() {
        PricingService off = svc(false);
        assertFalse(off.promoActive());
        PriceInfo p = off.price(5999, null, List.of("women"));
        assertEquals(5999, p.priceCents());
        assertFalse(p.onSale());
        assertFalse(p.excludedFromPromo());
        assertEquals(4999, off.price(5999, 4999, List.of("women")).priceCents());
        assertThrows(ApiException.class, () -> off.applyCode("BLACKFRIDAY", List.of(new PricedLine("a", 5000, true))));
    }

    @Test
    void outsideThePromotionWindowCodesAreUnknown() {
        PricingService after = PricingServiceTest.at("2026-12-01T08:00:00Z", PricingServiceTest.BF);
        assertFalse(after.promoActive());
        assertThrows(ApiException.class, () -> after.applyCode("BLACKFRIDAY", List.of(new PricedLine("a", 5000, true))));
    }
}
