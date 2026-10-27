package com.otterworks.fleet.eligibility;

import java.util.Collection;
import java.util.Map;

public interface CurrentCarLookup {

    Map<Long, String> currentRegistrations(Collection<Long> personIds);
}
