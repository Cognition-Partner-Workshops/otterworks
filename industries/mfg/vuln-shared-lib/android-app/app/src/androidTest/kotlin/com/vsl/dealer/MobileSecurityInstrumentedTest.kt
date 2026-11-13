package com.vsl.dealer

import android.content.Context
import android.security.NetworkSecurityPolicy
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test

class MobileSecurityInstrumentedTest {
    @Test fun cleartextIsRestrictedToEmulatorHost() {
        val policy = NetworkSecurityPolicy.getInstance()
        assertFalse(policy.isCleartextTrafficPermitted("dealer-api.example"))
        assertFalse(policy.isCleartextTrafficPermitted("example.com"))
        assertFalse(policy.isCleartextTrafficPermitted("sub.10.0.2.2"))
        assertTrue(policy.isCleartextTrafficPermitted("10.0.2.2"))
    }

    @Test fun keystoreTokenRoundTripHasNoPlaintext() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val prefs = context.getSharedPreferences("dealer_session", Context.MODE_PRIVATE)
        val store = PreferenceTokenStore(context)
        try {
            prefs.edit().clear().putString("access_token", "legacy").commit()
            assertNull(store.read())
            assertFalse(prefs.contains("access_token"))
            val token = "vsl-synthetic-instrumented-token"
            store.write(token)
            assertFalse(prefs.all.values.any { it.toString().contains(token) })
            assertEquals(token, PreferenceTokenStore(context).read())
            prefs.edit().putString("encrypted_access_token", "invalid").commit()
            assertNull(store.read())
            assertTrue(prefs.all.isEmpty())
        } finally { store.clear() }
    }
}
