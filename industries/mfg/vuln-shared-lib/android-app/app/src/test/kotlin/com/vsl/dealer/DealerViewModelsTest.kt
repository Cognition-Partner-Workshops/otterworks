package com.vsl.dealer

import com.vsl.dealer.api.Claim
import com.vsl.dealer.api.DealerClient
import com.vsl.dealer.api.InventoryItem
import com.vsl.dealer.api.SignInResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DealerViewModelsTest {
    private val dispatcher = StandardTestDispatcher()
    private lateinit var client: FakeClient

    @Before
    fun prepare() {
        Dispatchers.setMain(dispatcher)
        client = FakeClient()
    }

    @After
    fun close() {
        Dispatchers.resetMain()
    }

    @Test
    fun signInPublishesSessionAndClearsPassword() = runTest(dispatcher) {
        val model = SignInViewModel(client)
        model.emailChanged("dealer-ops@dealer.example")
        model.passwordChanged("vsl-synthetic-password")
        model.signIn()
        assertTrue(model.state.value.busy)
        advanceUntilIdle()
        assertEquals("D-1001", model.state.value.session?.dealerId)
        assertEquals("", model.state.value.password)
        assertFalse(model.state.value.busy)
        assertNull(model.state.value.error)
    }

    @Test
    fun signInRequiresBothFields() {
        val model = SignInViewModel(client)
        model.signIn()
        assertNotNull(model.state.value.error)
        assertFalse(model.state.value.busy)
        assertEquals(0, client.signInCalls)
    }

    @Test
    fun signInReportsFailureAndAllowsRetry() = runTest(dispatcher) {
        val model = SignInViewModel(client)
        model.emailChanged("dealer-ops@dealer.example")
        model.passwordChanged("vsl-synthetic-password")
        client.failRequests = true
        model.signIn()
        advanceUntilIdle()
        assertNotNull(model.state.value.error)
        assertNull(model.state.value.session)
        client.failRequests = false
        model.signIn()
        advanceUntilIdle()
        assertNotNull(model.state.value.session)
    }

    @Test
    fun repeatedSignInWhileBusyMakesOneRequest() = runTest(dispatcher) {
        val model = SignInViewModel(client)
        model.emailChanged("dealer-ops@dealer.example")
        model.passwordChanged("vsl-synthetic-password")
        model.signIn()
        model.signIn()
        advanceUntilIdle()
        assertEquals(1, client.signInCalls)
    }

    @Test
    fun inventoryPublishesVehicles() = runTest(dispatcher) {
        client.vehicles = listOf(InventoryItem("VSL1001", "Touring", 2027, "Available", 12300, ""))
        val model = InventoryViewModel(client)
        model.load("D-1001")
        assertTrue(model.state.value.loading)
        advanceUntilIdle()
        assertEquals("VSL1001", model.state.value.items.single().vin)
        assertEquals("D-1001", client.lastDealer)
        assertFalse(model.state.value.loading)
    }

    @Test
    fun inventoryAcceptsEmptyResponse() = runTest(dispatcher) {
        val model = InventoryViewModel(client)
        model.load("D-1001")
        advanceUntilIdle()
        assertTrue(model.state.value.items.isEmpty())
        assertNull(model.state.value.error)
    }

    @Test
    fun inventoryReportsFailure() = runTest(dispatcher) {
        client.failRequests = true
        val model = InventoryViewModel(client)
        model.load("D-1001")
        advanceUntilIdle()
        assertNotNull(model.state.value.error)
        assertFalse(model.state.value.loading)
    }

    @Test
    fun claimsPublishesRecords() = runTest(dispatcher) {
        client.records = listOf(client.claim)
        val model = ClaimsViewModel(client)
        model.load("D-1001")
        advanceUntilIdle()
        assertEquals("CL-1001", model.state.value.items.single().id)
    }

    @Test
    fun claimsAcceptsEmptyResponse() = runTest(dispatcher) {
        val model = ClaimsViewModel(client)
        model.load("D-1001")
        advanceUntilIdle()
        assertTrue(model.state.value.items.isEmpty())
        assertNull(model.state.value.error)
    }

    @Test
    fun claimsReportsFailureAndCanReload() = runTest(dispatcher) {
        client.failRequests = true
        val model = ClaimsViewModel(client)
        model.load("D-1001")
        advanceUntilIdle()
        assertNotNull(model.state.value.error)
        client.failRequests = false
        model.load("D-1001")
        advanceUntilIdle()
        assertNull(model.state.value.error)
    }

    @Test
    fun submissionRequiresFields() {
        val model = SubmitClaimViewModel(client)
        model.submit()
        assertNotNull(model.state.value.error)
        assertNull(model.state.value.submitted)
    }

    @Test
    fun submissionPublishesCreatedClaim() = runTest(dispatcher) {
        val model = SubmitClaimViewModel(client)
        model.vinChanged(" VSL1001 ")
        model.descriptionChanged(" Door adjustment ")
        model.submit()
        assertTrue(model.state.value.busy)
        advanceUntilIdle()
        assertEquals("VSL1001", model.state.value.submitted?.vin)
        assertEquals("Door adjustment", model.state.value.submitted?.description)
        assertFalse(model.state.value.busy)
    }

    @Test
    fun submissionReportsFailureWithoutLosingDraft() = runTest(dispatcher) {
        client.failRequests = true
        val model = SubmitClaimViewModel(client)
        model.vinChanged("VSL1001")
        model.descriptionChanged("Door adjustment")
        model.submit()
        advanceUntilIdle()
        assertNotNull(model.state.value.error)
        assertEquals("VSL1001", model.state.value.vin)
        assertEquals("Door adjustment", model.state.value.description)
        assertFalse(model.state.value.busy)
    }

    private class FakeClient : DealerClient {
        var failRequests = false
        var signInCalls = 0
        var lastDealer = ""
        var vehicles = emptyList<InventoryItem>()
        var records = emptyList<Claim>()
        val claim = Claim("CL-1001", "VSL1001", "Submitted", "Door adjustment", "2027-01-01T12:00:00Z")

        private fun checkRequest() {
            if (failRequests) throw IllegalStateException("Service unavailable")
        }

        override suspend fun signIn(email: String, password: String): SignInResponse {
            signInCalls++
            checkRequest()
            return SignInResponse("vsl-synthetic-test-token", "Bearer", 3600, "D-1001")
        }

        override suspend fun inventory(dealerId: String): List<InventoryItem> {
            checkRequest()
            lastDealer = dealerId
            return vehicles
        }

        override suspend fun claims(dealerId: String): List<Claim> {
            checkRequest()
            return records
        }

        override suspend fun submitClaim(vin: String, description: String): Claim {
            checkRequest()
            return claim.copy(vin = vin, description = description)
        }
    }
}
