package com.otterworks.fleet.eligibility;

import java.util.Collection;
import java.util.Map;

public final class NoCurrentCarLookup implements CurrentCarLookup {

    @Override
    public Map<Long, String> currentRegistrations(Collection<Long> personIds) {
        return Map.of();
    }
}
