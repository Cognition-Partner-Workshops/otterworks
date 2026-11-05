package com.bank.statements;

import static org.junit.Assert.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.junit.After;
import org.junit.Test;

public class ReferenceSecurityTest {
    private final String property = "bank.account.reference.secret";

    @After
    public void clearSecret() {
        System.clearProperty(property);
    }

    @Test
    public void referencesDependOnServerSecretNotOfflineAccountCandidates() {
        String account = "HG611000001";
        System.setProperty(property, UUID.randomUUID().toString());
        String first = Html.reference(account);
        assertEquals(first, Html.reference(account));
        assertNotEquals(UUID.nameUUIDFromBytes(account.getBytes(StandardCharsets.UTF_8)).toString(), first);
        System.setProperty(property, UUID.randomUUID().toString());
        assertNotEquals("Different server keys must produce different references", first, Html.reference(account));
    }

    @Test
    public void missingAndShortSecretsFailClosed() {
        for (String secret : new String[] {"", "short"}) {
            System.setProperty(property, secret);
            try {
                Html.reference("HG611000001");
                fail("Reference generation must require a server-side secret");
            } catch (IllegalStateException expected) {
                assertTrue(expected.getMessage().contains("BANK_ACCOUNT_REFERENCE_SECRET"));
                assertFalse(expected.getMessage().contains("HG611000001"));
            }
        }
    }
}
