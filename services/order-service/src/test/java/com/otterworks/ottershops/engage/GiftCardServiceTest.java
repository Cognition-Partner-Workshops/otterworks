package com.otterworks.ottershops.engage;

import com.otterworks.ottershops.common.ApiException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class GiftCardServiceTest {
    @Test
    void hashMatchesTheSeededFormat() {
        // V4 seeds encode(sha256('number:pin'), 'hex'); the service must produce the same digest.
        assertEquals("a28f9732c5f68e6987c3ba683298edf5bb3183d44edc710de1608cafeb06b4c1",
                GiftCardService.hash("6006491234567890", "1234"));
    }

    @Test
    void digitsStripsSpacesAndDashes() {
        assertEquals("6006491234567890", GiftCardService.digits("6006 4912-3456 7890"));
    }

    @Test
    void malformedInputIsRejectedBeforeLookup() {
        GiftCardService svc = new GiftCardService(null);
        ApiException e = assertThrows(ApiException.class, () -> svc.balance("1234", "12"));
        assertEquals("GIFT_CARD_INVALID", e.error());
    }
}
