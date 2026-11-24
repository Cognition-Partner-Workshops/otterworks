package com.otterworks.rating.audit;

import java.util.Map;

/** A quote an underwriter parked in the browser and sent back as JSON to carry on with. */
public record SavedQuote(String reference, Map<String, String> fields) {
}
