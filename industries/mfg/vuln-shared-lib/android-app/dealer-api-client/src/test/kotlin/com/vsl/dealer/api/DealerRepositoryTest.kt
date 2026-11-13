package com.vsl.dealer.api

import java.util.Base64
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException

class DealerRepositoryTest {
    private lateinit var server: MockWebServer
    private lateinit var tokens: MemoryTokens
    private lateinit var client: DealerClient
    private val apiKey = "vsl-synthetic-test-api-key"
    private val expectedToken = "v1.eyJzdWIiOiJkZWFsZXItb3BzQGRlYWxlci5leGFtcGxlIiwiZGVhbGVyIjoiRC0xMDAxIiwicm9sZXMiOlsiZGVhbGVyIl0sImlhdCI6MTc5ODc2MTYwMCwiZXhwIjoxNzk4NzY1MjAwfQ.aQiSk3ln-G_hMxS28Rm8xvC-7P0"
    private val claimJson = """{"id":"CL-1001","vin":"VSL00000000001001","status":"Submitted","description":"Door adjustment","submittedAt":"2027-01-01T12:00:00Z"}"""

    @Before
    fun prepare() {
        server = MockWebServer()
        server.start()
        tokens = MemoryTokens()
        client = DealerRepository.create(server.url("/").toString(), apiKey, tokens)
    }

    @After
    fun close() {
        server.shutdown()
    }

    private fun enqueue(body: String, status: Int = 200) {
        server.enqueue(MockResponse().setResponseCode(status)
            .setHeader("Content-Type", "application/json").setBody(body))
    }

    private fun signInBody(): String =
        requireNotNull(javaClass.getResource("/identity/signin-response.json")).readText()

    @Test
    fun signInReadsIdentityContractAndStoresToken() = runBlocking {
        enqueue(signInBody())
        val session = client.signIn("dealer-ops@dealer.example", "vsl-synthetic-password")
        assertEquals(expectedToken, session.accessToken)
        assertEquals("Bearer", session.tokenType)
        assertEquals(3600L, session.expiresIn)
        assertEquals("D-1001", session.dealerId)
        assertEquals(expectedToken, tokens.read())
        assertTrue(session.accessToken.matches(Regex("v1\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")))
        val payload = String(Base64.getUrlDecoder().decode(session.accessToken.split('.')[1]), Charsets.UTF_8)
        val claims = Json.parseToJsonElement(payload).jsonObject
        assertEquals("dealer-ops@dealer.example", claims.getValue("sub").jsonPrimitive.content)
        assertEquals("D-1001", claims.getValue("dealer").jsonPrimitive.content)
        assertEquals(listOf("dealer"), claims.getValue("roles").jsonArray.map { it.jsonPrimitive.content })
        assertEquals("1798761600", claims.getValue("iat").jsonPrimitive.content)
        assertEquals("1798765200", claims.getValue("exp").jsonPrimitive.content)
        val request = requireNotNull(server.takeRequest(2, TimeUnit.SECONDS))
        assertEquals("/api/identity/signin", request.path)
        assertEquals("POST", request.method)
        assertEquals(apiKey, request.getHeader("X-Api-Key"))
        assertNull(request.getHeader("Authorization"))
        assertEquals(
            Json.parseToJsonElement("""{"email":"dealer-ops@dealer.example","password":"vsl-synthetic-password"}"""),
            Json.parseToJsonElement(request.body.readUtf8()),
        )
    }

    @Test
    fun nextInventoryAndClaimsCallsCarryIdentityTokenVerbatim() = runBlocking {
        enqueue(signInBody())
        enqueue("[]")
        enqueue("[]")
        client.signIn("dealer-ops@dealer.example", "vsl-synthetic-password")
        client.inventory("D-1001")
        client.claims("D-1001")
        server.takeRequest()
        for (path in listOf("/api/dealer/inventory?dealerId=D-1001", "/api/warranty/claims?dealerId=D-1001")) {
            val request = server.takeRequest()
            assertEquals(path, request.path)
            assertEquals("GET", request.method)
            assertEquals("Bearer $expectedToken", request.getHeader("Authorization"))
            assertEquals(apiKey, request.getHeader("X-Api-Key"))
        }
    }

    @Test
    fun inventoryParsesVehicleFields() = runBlocking {
        enqueue("""[{"vin":"VSL00000000001001","model":"Touring","year":2027,"status":"Available","priceCents":3245000,"imageUrl":"https://images.dealer.example/1001.jpg"}]""")
        val vehicle = client.inventory("D-1001").single()
        assertEquals("VSL00000000001001", vehicle.vin)
        assertEquals("Touring", vehicle.model)
        assertEquals(2027, vehicle.year)
        assertEquals("Available", vehicle.status)
        assertEquals(3245000L, vehicle.priceCents)
        assertEquals("https://images.dealer.example/1001.jpg", vehicle.imageUrl)
    }

    @Test
    fun claimsParsesAllFields() = runBlocking {
        enqueue("[$claimJson]")
        val claim = client.claims("D-1001").single()
        assertEquals("CL-1001", claim.id)
        assertEquals("VSL00000000001001", claim.vin)
        assertEquals("Submitted", claim.status)
        assertEquals("Door adjustment", claim.description)
        assertEquals("2027-01-01T12:00:00Z", claim.submittedAt)
    }

    @Test
    fun submitClaimPostsBodyAndParsesCreatedResponse() = runBlocking {
        tokens.write(expectedToken)
        enqueue(claimJson, 201)
        val claim = client.submitClaim("VSL00000000001001", "Door adjustment")
        assertEquals("CL-1001", claim.id)
        val request = server.takeRequest()
        assertEquals("/api/warranty/claims", request.path)
        assertEquals("POST", request.method)
        assertEquals("Bearer $expectedToken", request.getHeader("Authorization"))
        assertEquals(apiKey, request.getHeader("X-Api-Key"))
        assertEquals(
            Json.parseToJsonElement("""{"vin":"VSL00000000001001","description":"Door adjustment"}"""),
            Json.parseToJsonElement(request.body.readUtf8()),
        )
    }

    @Test
    fun emptyCollectionsAreReturned() = runBlocking {
        enqueue("[]")
        enqueue("[]")
        assertTrue(client.inventory("D-1001").isEmpty())
        assertTrue(client.claims("D-1001").isEmpty())
    }

    @Test
    fun rejectedSignInDoesNotStoreToken() = runBlocking {
        enqueue("{}", 401)
        try {
            client.signIn("dealer-ops@dealer.example", "vsl-synthetic-password")
            fail("Expected rejected sign in")
        } catch (error: HttpException) {
            assertEquals(401, error.code())
        }
        assertNull(tokens.read())
    }

    @Test
    fun rejectedInventoryPropagatesStatus() = runBlocking {
        enqueue("{}", 401)
        try {
            client.inventory("D-1001")
            fail("Expected rejected request")
        } catch (error: HttpException) {
            assertEquals(401, error.code())
        }
    }

    @Test
    fun signInDoesNotSendPreviousSession() = runBlocking {
        tokens.write(expectedToken)
        enqueue(signInBody())
        client.signIn("dealer-ops@dealer.example", "vsl-synthetic-password")
        assertNull(server.takeRequest().getHeader("Authorization"))
    }

    @Test
    fun inventoryWithoutSessionOmitsBearerHeader() = runBlocking {
        enqueue("[]")
        client.inventory("D-1001")
        assertNull(server.takeRequest().getHeader("Authorization"))
    }

    @Test
    fun tokenStoreCanClearSession() {
        tokens.write(expectedToken)
        tokens.clear()
        assertNull(tokens.read())
    }

    @Test
    fun rejectedClaimsPropagatesStatus() = runBlocking {
        enqueue("{}", 401)
        try {
            client.claims("D-1001")
            fail("Expected rejected request")
        } catch (error: HttpException) {
            assertEquals(401, error.code())
        }
    }

    @Test
    fun rejectedSubmissionPropagatesStatus() = runBlocking {
        enqueue("{}", 422)
        try {
            client.submitClaim("VSL00000000001001", "Door adjustment")
            fail("Expected rejected submission")
        } catch (error: HttpException) {
            assertEquals(422, error.code())
        }
    }

    @Test
    fun malformedSignInDoesNotReplaceSession() = runBlocking {
        tokens.write(expectedToken)
        enqueue("""{"accessToken":"vsl-synthetic-incomplete"}""")
        try {
            client.signIn("dealer-ops@dealer.example", "vsl-synthetic-password")
            fail("Expected incomplete response")
        } catch (error: kotlinx.serialization.SerializationException) {
            assertEquals(expectedToken, tokens.read())
        }
    }

    @Test
    fun additionalIdentityFieldsAreAccepted() = runBlocking {
        enqueue(signInBody().trim().dropLast(1) + ""","region":"north"}""")
        assertEquals(expectedToken, client.signIn(
            "dealer-ops@dealer.example", "vsl-synthetic-password",
        ).accessToken)
    }

    @Test
    fun dealerQueryIsEncodedByRetrofit() = runBlocking {
        enqueue("[]")
        client.inventory("D 1001&region=north")
        val request = server.takeRequest()
        assertEquals("D 1001&region=north", request.requestUrl?.queryParameter("dealerId"))
        assertEquals(setOf("dealerId"), request.requestUrl?.queryParameterNames)
    }

    @Test
    fun updatedStoreValueIsReadForEveryCall() = runBlocking {
        enqueue("[]")
        enqueue("[]")
        tokens.write(expectedToken)
        client.inventory("D-1001")
        tokens.clear()
        client.claims("D-1001")
        assertEquals("Bearer $expectedToken", server.takeRequest().getHeader("Authorization"))
        assertNull(server.takeRequest().getHeader("Authorization"))
    }

    @Test
    fun blankSessionDoesNotAddBearerHeader() = runBlocking {
        tokens.write(" ")
        enqueue("[]")
        client.claims("D-1001")
        assertNull(server.takeRequest().getHeader("Authorization"))
    }

    private class MemoryTokens : TokenStore {
        private var token: String? = null
        override fun read(): String? = token
        override fun write(token: String) { this.token = token }
        override fun clear() { token = null }
    }
}
