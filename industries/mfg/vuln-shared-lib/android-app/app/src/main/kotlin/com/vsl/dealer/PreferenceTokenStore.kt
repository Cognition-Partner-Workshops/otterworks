package com.vsl.dealer

import android.content.Context
import com.vsl.dealer.api.TokenStore

class PreferenceTokenStore(context: Context) : TokenStore {
    private val preferences = context.getSharedPreferences("dealer_session", Context.MODE_PRIVATE)

    override fun read(): String? = preferences.getString("access_token", null)

    override fun write(token: String) {
        preferences.edit().putString("access_token", token).apply()
    }

    override fun clear() {
        preferences.edit().remove("access_token").apply()
    }
}
