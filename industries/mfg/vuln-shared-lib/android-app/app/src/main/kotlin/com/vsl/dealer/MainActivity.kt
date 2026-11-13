package com.vsl.dealer

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import com.vsl.dealer.api.DealerRepository

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val client = DealerRepository.create(
            BuildConfig.API_BASE_URL,
            tokens = PreferenceTokenStore(applicationContext),
        )
        setContent {
            MaterialTheme {
                DealerApp(client)
            }
        }
    }
}
