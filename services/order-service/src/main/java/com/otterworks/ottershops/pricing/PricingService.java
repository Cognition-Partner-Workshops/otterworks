package com.otterworks.ottershops.pricing;

import com.otterworks.ottershops.common.ApiException;
import com.otterworks.ottershops.common.Money;
import java.time.Clock;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;

@Service
public class PricingService {
    private final Promotion promotion;
    private final Clock clock;

    public PricingService(Promotion promotion, Clock clock) {
        this.promotion = promotion;
        this.clock = clock;
    }

    public boolean promoActive() {
        return promotion != null && promotion.activeAt(clock.instant());
    }

    public Optional<Promotion> activePromotion() {
        return promoActive() ? Optional.of(promotion) : Optional.empty();
    }

    public boolean excluded(Collection<String> collections) {
        return promotion != null && collections.stream().anyMatch(promotion.excludedCollections()::contains);
    }

    public boolean eligible(Collection<String> collections) {
        return promoActive() && !excluded(collections);
    }

    public PriceInfo price(int listCents, Integer markdownCents, Collection<String> collections) {
        boolean eligible = eligible(collections);
        int price = listCents;
        if (markdownCents != null && markdownCents < price) {
            price = markdownCents;
        }
        if (eligible) {
            int promoPrice = listCents - Money.percentOf(listCents, promotion.percentOff());
            price = Math.min(price, promoPrice);
        }
        int pct = price < listCents ? (int) ((listCents - price) * 100L / listCents) : 0;
        return new PriceInfo(listCents, price, price < listCents, eligible, promoActive() && excluded(collections), pct);
    }

    /**
     * Applies a checkout code to the bag. Unknown codes and codes below their minimum throw a 400.
     * The discount is split across qualifying lines in proportion to their value; the rounding
     * remainder goes to the last qualifying line, so the split always sums to the total.
     */
    public CodeDiscount applyCode(String rawCode, List<PricedLine> lines) {
        PromoCode code = findCode(rawCode);
        long subtotal = lines.stream().mapToLong(PricedLine::lineTotalCents).sum();
        if (subtotal < code.minSubtotalCents()) {
            throw new ApiException(org.springframework.http.HttpStatus.BAD_REQUEST, "PROMO_MINIMUM_NOT_MET",
                    "Add " + Money.format(code.minSubtotalCents() - subtotal) + " more to use " + code.code(),
                    Map.of("code", code.code(), "shortfallCents", code.minSubtotalCents() - subtotal));
        }
        List<PricedLine> qualifying = lines.stream()
                .filter(l -> code.appliesToExcluded() || l.eligible())
                .filter(l -> l.lineTotalCents() > 0)
                .toList();
        if (qualifying.isEmpty()) {
            throw ApiException.badRequest("PROMO_NOT_APPLICABLE", code.code() + " doesn't apply to the items in your bag");
        }
        long base = qualifying.stream().mapToLong(PricedLine::lineTotalCents).sum();
        int total = Money.percentOf(base, code.percentOff());
        Map<String, Integer> perLine = new LinkedHashMap<>();
        lines.forEach(l -> perLine.put(l.key(), 0));
        int allocated = 0;
        for (int i = 0; i < qualifying.size(); i++) {
            PricedLine l = qualifying.get(i);
            int share = i == qualifying.size() - 1
                    ? total - allocated
                    : (int) (total * l.lineTotalCents() / base);
            perLine.put(l.key(), share);
            allocated += share;
        }
        return new CodeDiscount(code, total, perLine);
    }

    public PromoCode findCode(String rawCode) {
        String normalized = rawCode == null ? "" : rawCode.trim().toUpperCase(Locale.ROOT);
        if (normalized.isEmpty()) {
            throw ApiException.badRequest("PROMO_INVALID", "Enter a promo code");
        }
        return activePromotion().stream()
                .flatMap(p -> p.codes().stream())
                .filter(c -> c.code().equalsIgnoreCase(normalized))
                .findFirst()
                .orElseThrow(() -> ApiException.badRequest("PROMO_INVALID", "We don't recognize the code " + normalized));
    }
}
