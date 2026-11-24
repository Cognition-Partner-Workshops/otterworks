package com.otterworks.rating.audit;

import java.io.Serializable;
import java.util.Map;

/** A quote an underwriter parked in the browser and sent back to carry on with. */
public class SavedQuote implements Serializable {

    private static final long serialVersionUID = 1L;

    private final String reference;
    private final Map<String, String> fields;

    public SavedQuote(String reference, Map<String, String> fields) {
        this.reference = reference;
        this.fields = fields;
    }

    public String reference() {
        return reference;
    }

    public Map<String, String> fields() {
        return fields;
    }
}
