package com.otterworks.ottershops.account;

import com.otterworks.ottershops.common.ApiException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class AddressServiceTest {
    static AddressService.Input in(String state, String zip) {
        return new AddressService.Input(" Home ", " Maya Otter ", " 1 Main St ", " ", " Denver ", state, zip, null, null);
    }

    @Test
    void validAddressIsNormalized() {
        AddressService.Input out = AddressService.validate(in("co", "80202"));
        assertEquals("CO", out.state());
        assertEquals("Maya Otter", out.name());
        assertEquals("Home", out.label());
        assertNull(out.line2());
    }

    @Test
    void badStateAndZipAreRejected() {
        assertEquals("STATE_INVALID", assertThrows(ApiException.class, () -> AddressService.validate(in("ZZ", "80202"))).error());
        assertEquals("ZIP_INVALID", assertThrows(ApiException.class, () -> AddressService.validate(in("CO", "8020"))).error());
    }

    @Test
    void missingStreetIsRejected() {
        AddressService.Input bad = new AddressService.Input(null, "Maya", "", null, "Denver", "CO", "80202", null, null);
        assertEquals("ADDRESS_INCOMPLETE", assertThrows(ApiException.class, () -> AddressService.validate(bad)).error());
    }
}
