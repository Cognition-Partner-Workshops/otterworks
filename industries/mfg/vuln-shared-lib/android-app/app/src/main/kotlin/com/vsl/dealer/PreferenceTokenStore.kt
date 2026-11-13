package com.vsl.dealer

import android.content.Context
import com.vsl.dealer.api.TokenStore

interface TokenPreferences {
    fun get(key: String): String?
    fun put(key: String, value: String)
    fun remove(key: String)
}

interface TokenCipher {
    fun encrypt(token: String): String
    fun decrypt(value: String): String
}

class PreferenceTokenStore(
    private val preferences: TokenPreferences,
    private val cipher: TokenCipher,
) : TokenStore {
    constructor(context: Context) : this(object : TokenPreferences {
        private val prefs = context.getSharedPreferences("dealer_session", Context.MODE_PRIVATE)
        override fun get(key: String): String? = prefs.getString(key, null)
        override fun put(key: String, value: String) { prefs.edit().putString(key, value).apply() }
        override fun remove(key: String) { prefs.edit().remove(key).apply() }
    }, KeystoreTokenCipher())

    override fun read(): String? {
        preferences.remove("access_token")
        return try {
            preferences.get("encrypted_access_token")?.let(cipher::decrypt)
        } catch (_: Exception) {
            clear()
            null
        }
    }

    override fun write(token: String) {
        clear()
        preferences.put("encrypted_access_token", cipher.encrypt(token))
    }

    override fun clear() {
        preferences.remove("access_token")
        preferences.remove("encrypted_access_token")
    }
}
