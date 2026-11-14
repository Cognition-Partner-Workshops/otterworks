package com.otterworks.notification.routes

import com.auth0.jwt.JWT
import com.auth0.jwt.algorithms.Algorithm
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.model.Notification
import com.otterworks.notification.plugins.ACCESS_TOKEN_QUERY_PARAM
import com.otterworks.notification.plugins.configureSecurity
import com.otterworks.notification.websocket.WebSocketManager
import io.ktor.client.HttpClient
import io.ktor.client.plugins.websocket.webSocket
import io.ktor.client.request.header
import io.ktor.http.HttpHeaders
import io.ktor.serialization.kotlinx.json.json
import io.ktor.server.application.install
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty
import io.ktor.server.plugins.contentnegotiation.ContentNegotiation
import io.ktor.server.routing.routing
import io.ktor.server.testing.ApplicationTestBuilder
import io.ktor.server.testing.testApplication
import io.ktor.server.websocket.WebSockets
import io.ktor.websocket.Frame
import io.ktor.websocket.readText
import kotlinx.coroutines.runBlocking
import java.net.Socket
import java.time.Instant
import java.util.UUID
import java.util.Date
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import io.ktor.client.plugins.websocket.WebSockets as ClientWebSockets

class NotificationWebSocketAuthTest {

    private val secret = randomSecret()
    private val alice = "11111111-1111-1111-1111-111111111111"
    private val bob = "22222222-2222-2222-2222-222222222222"

    private fun randomSecret() = UUID.randomUUID().toString().repeat(2)

    private fun config(jwtSecret: String? = secret) = AppConfig(
        port = 8086,
        awsRegion = "us-east-1",
        awsEndpointUrl = null,
        sqsQueueUrl = "http://localhost:4566/000000000000/test-queue",
        snsTopicArn = "arn:aws:sns:us-east-1:000000000000:test-topic",
        dynamoDbTableNotifications = "test-notifications",
        dynamoDbTablePreferences = "test-preferences",
        sesFromEmail = "test@otterworks.io",
        sqsPollIntervalMs = 1000,
        sqsMaxMessages = 10,
        sqsWaitTimeSeconds = 5,
        jwtSecret = jwtSecret,
    )

    private fun token(
        subject: String,
        algorithm: Algorithm = Algorithm.HMAC384(secret),
        type: String = "access",
        expiresAt: Instant = Instant.now().plusSeconds(3600),
    ): String = JWT.create()
        .withSubject(subject)
        .withClaim("type", type)
        .withIssuedAt(Date.from(Instant.now().minusSeconds(60)))
        .withExpiresAt(Date.from(expiresAt))
        .sign(algorithm)

    private fun notificationFor(userId: String) = Notification(
        id = "n-1",
        userId = userId,
        type = "file_shared",
        title = "File shared",
        message = "A file was shared with you",
        createdAt = "2024-01-01T00:00:00Z",
    )

    private fun wsTest(
        manager: WebSocketManager = WebSocketManager(),
        jwtSecret: String? = secret,
        block: suspend ApplicationTestBuilder.(WebSocketManager) -> Unit,
    ) = testApplication {
        application {
            install(ContentNegotiation) { json() }
            install(WebSockets)
            configureSecurity(config(jwtSecret))
            routing { notificationWebSocket(manager) }
        }
        block(manager)
    }

    private fun ApplicationTestBuilder.wsClient(): HttpClient = createClient { install(ClientWebSockets) }

    /**
     * Rejection cases run against a real Netty server: the test engine's WebSocket client hides the HTTP
     * status of a refused upgrade, and that status is exactly what these tests assert.
     */
    private fun handshakeTest(
        manager: WebSocketManager = WebSocketManager(),
        jwtSecret: String? = secret,
        block: (handshake: (path: String, bearer: String?) -> Int) -> Unit,
    ) {
        val server = embeddedServer(Netty, port = 0, host = "127.0.0.1") {
            install(ContentNegotiation) { json() }
            install(WebSockets)
            configureSecurity(config(jwtSecret))
            routing { notificationWebSocket(manager) }
        }.start(wait = false)
        try {
            val port = runBlocking { server.resolvedConnectors().first().port }
            block { path, bearer -> upgradeStatus(port, path, bearer) }
        } finally {
            server.stop(0, 0)
        }
    }

    /** Sends a raw RFC 6455 upgrade request and returns the status code of the server's reply. */
    private fun upgradeStatus(port: Int, path: String, bearer: String?): Int =
        Socket("127.0.0.1", port).use { socket ->
            socket.soTimeout = 5000
            val request = buildString {
                append("GET $path HTTP/1.1\r\n")
                append("Host: 127.0.0.1:$port\r\n")
                append("Connection: Upgrade\r\n")
                append("Upgrade: websocket\r\n")
                append("Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n")
                append("Sec-WebSocket-Version: 13\r\n")
                bearer?.let { append("Authorization: Bearer $it\r\n") }
                append("\r\n")
            }
            socket.getOutputStream().apply { write(request.toByteArray()); flush() }
            val statusLine = socket.getInputStream().bufferedReader().readLine()
            statusLine.split(" ")[1].toInt()
        }

    @Test
    fun `unauthenticated connect to a victim's stream is rejected`() {
        val manager = WebSocketManager()
        handshakeTest(manager) { handshake ->
            assertEquals(401, handshake("/ws/notifications/$bob", null))
            assertEquals(401, handshake("/ws/notifications", null))
            assertEquals(401, handshake("/ws/notifications/$bob?user_id=$bob", null))
        }
        assertFalse(manager.isUserConnected(bob))
    }

    @Test
    fun `cross-user subscription is denied even with a valid token`() = runBlocking {
        val manager = WebSocketManager()
        handshakeTest(manager) { handshake ->
            assertEquals(403, handshake("/ws/notifications/$bob", token(alice)))
            assertEquals(403, handshake("/ws/notifications/$bob?$ACCESS_TOKEN_QUERY_PARAM=${token(alice)}", null))
        }
        assertFalse(manager.isUserConnected(bob))
        assertEquals(0, manager.pushNotification(bob, notificationFor(bob)))
    }

    @Test
    fun `forged, expired, refresh and unsigned tokens are rejected`() {
        val manager = WebSocketManager()
        val forged = token(bob, algorithm = Algorithm.HMAC384(randomSecret()))
        val expired = token(bob, expiresAt = Instant.now().minusSeconds(120))
        val refresh = token(bob, type = "refresh")
        val unsigned = JWT.create().withSubject(bob).sign(Algorithm.none())

        handshakeTest(manager) { handshake ->
            listOf(forged, expired, refresh, unsigned, "not-a-jwt").forEach { bad ->
                assertEquals(401, handshake("/ws/notifications/$bob", bad), bad)
                assertEquals(401, handshake("/ws/notifications?$ACCESS_TOKEN_QUERY_PARAM=$bad", null), bad)
            }
        }
        assertFalse(manager.isUserConnected(bob))
    }

    @Test
    fun `every connection is rejected when no JWT secret is configured`() {
        val manager = WebSocketManager()
        handshakeTest(manager, jwtSecret = null) { handshake ->
            assertEquals(401, handshake("/ws/notifications/$alice", token(alice)))
        }
        assertFalse(manager.isUserConnected(alice))
    }

    @Test
    fun `own stream upgrades over a real server`() {
        handshakeTest { handshake ->
            assertEquals(101, handshake("/ws/notifications/$alice", token(alice)))
            assertEquals(101, handshake("/ws/notifications?$ACCESS_TOKEN_QUERY_PARAM=${token(alice)}", null))
        }
    }

    @Test
    fun `authenticated user streams only their own notifications via header token`() = wsTest { manager ->
        wsClient().webSocket("/ws/notifications", request = {
            header(HttpHeaders.Authorization, "Bearer ${token(alice)}")
        }) {
            send(Frame.Text("ping"))
            assertEquals("pong", (incoming.receive() as Frame.Text).readText())
            assertTrue(manager.isUserConnected(alice))
            assertFalse(manager.isUserConnected(bob))

            assertEquals(0, manager.pushNotification(bob, notificationFor(bob)))
            assertEquals(1, manager.pushNotification(alice, notificationFor(alice)))
            val received = (incoming.receive() as Frame.Text).readText()
            assertTrue(received.contains("\"userId\":\"$alice\""), received)
        }
    }

    @Test
    fun `legacy path with own userId and query token still works for every HMAC size`() = wsTest { manager ->
        listOf(Algorithm.HMAC256(secret), Algorithm.HMAC384(secret), Algorithm.HMAC512(secret)).forEach { alg ->
            wsClient().webSocket("/ws/notifications/$alice?$ACCESS_TOKEN_QUERY_PARAM=${token(alice, alg)}") {
                send(Frame.Text("ping"))
                assertEquals("pong", (incoming.receive() as Frame.Text).readText())
                assertTrue(manager.isUserConnected(alice))
            }
        }
    }
}
