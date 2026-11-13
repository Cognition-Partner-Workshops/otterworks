package com.vsl.dealer

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.*
import org.junit.Test

class MobileSecurityTest {
    @Test fun noEmbeddedApiKey() {
        assertFalse(BuildConfig::class.java.declaredFields.any { it.name.contains("API_KEY") })
    }

    @Test fun cleartextIsDeniedByDefault() {
        val manifest = DocumentBuilderFactory.newInstance().newDocumentBuilder()
            .parse(File("src/main/AndroidManifest.xml"))
        val app = manifest.getElementsByTagName("application").item(0).attributes
        assertNotEquals("true", app.getNamedItem("android:usesCleartextTraffic")?.nodeValue)
        assertEquals("@xml/network_security_config", app.getNamedItem("android:networkSecurityConfig")?.nodeValue)
        for (variant in listOf("main", "debug")) {
            val config = DocumentBuilderFactory.newInstance().newDocumentBuilder()
                .parse(File("src/$variant/res/xml/network_security_config.xml"))
            assertEquals("false", config.getElementsByTagName("base-config").item(0)
                .attributes.getNamedItem("cleartextTrafficPermitted").nodeValue)
            val domains = config.getElementsByTagName("domain")
            assertEquals(if (variant == "debug") 1 else 0, domains.length)
            if (domains.length > 0) assertEquals("10.0.2.2", domains.item(0).textContent)
        }
    }

    private class MemoryPreferences : TokenPreferences {
        val values = mutableMapOf<String, String>()
        override fun get(key: String) = values[key]
        override fun put(key: String, value: String) { values[key] = value }
        override fun remove(key: String) { values.remove(key) }
    }
    private val cipher = object : TokenCipher {
        override fun encrypt(token: String) = "encrypted:" + token.reversed()
        override fun decrypt(value: String): String {
            require(value.startsWith("encrypted:"))
            return value.removePrefix("encrypted:").reversed()
        }
    }

    @Test fun tokensAreEncryptedAndLegacyValuesDiscarded() {
        val prefs = MemoryPreferences()
        val store = PreferenceTokenStore(prefs, cipher)
        prefs.put("access_token", "legacy")
        assertNull(store.read())
        assertTrue(prefs.values.isEmpty())
        prefs.put("access_token", "legacy")
        store.write("secret-token")
        assertFalse(prefs.values.containsValue("secret-token"))
        assertFalse(prefs.values.containsKey("access_token"))
        assertEquals("secret-token", store.read())
        prefs.put("access_token", "legacy")
        store.clear()
        assertTrue(prefs.values.isEmpty())
        assertNull(store.read())
    }

    @Test fun corruptValueIsCleared() {
        val prefs = MemoryPreferences()
        val store = PreferenceTokenStore(prefs, cipher)
        prefs.put("encrypted_access_token", "corrupt")
        prefs.put("access_token", "legacy")
        assertNull(store.read())
        assertTrue(prefs.values.isEmpty())
    }

    @Test fun failedEncryptionDoesNotLeaveOldCredentials() {
        val prefs = MemoryPreferences()
        prefs.put("access_token", "legacy")
        prefs.put("encrypted_access_token", "old")
        val store = PreferenceTokenStore(prefs, object : TokenCipher {
            override fun encrypt(token: String): String = error("unavailable")
            override fun decrypt(value: String): String = error("unavailable")
        })
        try { store.write("new"); fail("Expected encryption failure") } catch (_: IllegalStateException) {}
        assertTrue(prefs.values.isEmpty())
    }
}
