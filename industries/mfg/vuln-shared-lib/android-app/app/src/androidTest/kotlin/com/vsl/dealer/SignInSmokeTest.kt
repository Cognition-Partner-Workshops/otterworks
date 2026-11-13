package com.vsl.dealer

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import com.vsl.dealer.api.Claim
import com.vsl.dealer.api.DealerClient
import com.vsl.dealer.api.InventoryItem
import com.vsl.dealer.api.SignInResponse
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class SignInSmokeTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun signInCallsClientAndOpensInventory() {
        val client = StubClient()
        compose.setContent { MaterialTheme { DealerApp(client) } }
        compose.onNodeWithText("Email").performTextInput("dealer-ops@dealer.example")
        compose.onNodeWithText("Password").performTextInput("vsl-synthetic-password")
        compose.onNodeWithText("Sign in").performClick()
        compose.waitUntil(10_000) { client.inventoryRequested }
        compose.onNodeWithText("Inventory · D-1001").assertExists()
        compose.onNodeWithText("No vehicles available.").assertExists()
        assertEquals("dealer-ops@dealer.example", client.email)
        assertEquals("vsl-synthetic-password", client.password)
    }

    private class StubClient : DealerClient {
        var email = ""
        var password = ""
        @Volatile var inventoryRequested = false
        override suspend fun signIn(email: String, password: String): SignInResponse {
            this.email = email
            this.password = password
            return SignInResponse("vsl-synthetic-ui-token", "Bearer", 3600, "D-1001")
        }
        override suspend fun inventory(dealerId: String): List<InventoryItem> {
            inventoryRequested = true
            return emptyList()
        }
        override suspend fun claims(dealerId: String): List<Claim> = emptyList()
        override suspend fun submitClaim(vin: String, description: String): Claim =
            Claim("CL-1001", vin, "Submitted", description, "2027-01-01T12:00:00Z")
    }
}
