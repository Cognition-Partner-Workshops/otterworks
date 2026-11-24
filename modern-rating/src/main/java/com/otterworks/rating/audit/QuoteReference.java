package com.otterworks.rating.audit;

import com.otterworks.rating.model.Quote;
import com.otterworks.rating.util.Sha256;

/** Short reference an underwriter reads back over the phone to find a saved quote. */
public final class QuoteReference {

    private QuoteReference() {}

    public static String of(Quote quote) {
        return Sha256.hex(quote.asLine()).substring(0, 16);
    }
}
