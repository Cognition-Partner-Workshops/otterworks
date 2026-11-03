package com.otterworks.ottershops.pricing;

import java.time.Instant;
import java.util.List;

public record Promotion(
        boolean enabled,
        String id,
        String name,
        String headline,
        String subhead,
        String bannerText,
        Instant startsAt,
        Instant endsAt,
        int percentOff,
        List<String> excludedCollections,
        List<PromoCode> codes) {

    public Promotion {
        excludedCollections = excludedCollections == null ? List.of() : List.copyOf(excludedCollections);
        codes = codes == null ? List.of() : List.copyOf(codes);
    }

    public boolean activeAt(Instant now) {
        return enabled && startsAt != null && endsAt != null && !now.isBefore(startsAt) && now.isBefore(endsAt);
    }

    public Promotion withEnabled(boolean value) {
        return new Promotion(value, id, name, headline, subhead, bannerText, startsAt, endsAt, percentOff, excludedCollections, codes);
    }
}
