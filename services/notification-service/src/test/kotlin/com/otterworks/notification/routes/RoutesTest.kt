package com.otterworks.notification.routes

import com.otterworks.notification.service.NotificationService
import com.otterworks.notification.websocket.WebSocketManager
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.statement.bodyAsText
import io.ktor.http.HttpStatusCode
import io.ktor.serialization.kotlinx.json.json
import io.ktor.server.application.install
import io.ktor.server.plugins.contentnegotiation.ContentNegotiation
import io.ktor.server.testing.ApplicationTestBuilder
import io.ktor.server.testing.testApplication
import io.ktor.server.websocket.WebSockets
import io.micrometer.prometheus.PrometheusConfig
import io.micrometer.prometheus.PrometheusMeterRegistry
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.koin.core.context.stopKoin
import org.koin.dsl.module
import org.koin.ktor.plugin.Koin
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals

// The api-gateway forwards the authenticated user as the X-User-ID header (from the JWT
// "sub" claim), and the web app sends pagination as page/pageSize.
class RoutesTest {

    private val notificationService = mockk<NotificationService>(relaxed = true)

    @AfterTest
    fun tearDown() {
        stopKoin()
    }

    private fun ApplicationTestBuilder.setUp() {
        application {
            install(ContentNegotiation) { json() }
            install(WebSockets)
            install(Koin) {
                modules(module {
                    single { notificationService }
                    single { mockk<WebSocketManager>(relaxed = true) }
                })
            }
            configureRouting(PrometheusMeterRegistry(PrometheusConfig.DEFAULT))
        }
    }

    @Test
    fun `unread-count uses the X-User-ID header forwarded by the gateway`() = testApplication {
        setUp()
        coEvery { notificationService.getUnreadCount("user-1") } returns 3

        val response = client.get("/api/v1/notifications/unread-count") {
            header("X-User-ID", "user-1")
        }

        assertEquals(HttpStatusCode.OK, response.status)
        val body = Json.parseToJsonElement(response.bodyAsText()).jsonObject
        assertEquals(3, body["unreadCount"]!!.jsonPrimitive.int)
    }

    @Test
    fun `list uses the X-User-ID header and honours the web app's pageSize parameter`() = testApplication {
        setUp()
        coEvery { notificationService.getNotifications("user-1", 2, 5) } returns Pair(emptyList(), 12)

        val response = client.get("/api/v1/notifications?page=2&pageSize=5") {
            header("X-User-ID", "user-1")
        }

        assertEquals(HttpStatusCode.OK, response.status)
        coVerify { notificationService.getNotifications("user-1", 2, 5) }
        val body = Json.parseToJsonElement(response.bodyAsText()).jsonObject
        assertEquals(5, body["pageSize"]!!.jsonPrimitive.int)
    }

    @Test
    fun `list still accepts page_size`() = testApplication {
        setUp()
        coEvery { notificationService.getNotifications("user-1", 1, 7) } returns Pair(emptyList(), 0)

        val response = client.get("/api/v1/notifications?page=1&page_size=7") {
            header("X-User-ID", "user-1")
        }

        assertEquals(HttpStatusCode.OK, response.status)
        coVerify { notificationService.getNotifications("user-1", 1, 7) }
    }

    @Test
    fun `requests without a user identity are rejected`() = testApplication {
        setUp()

        assertEquals(HttpStatusCode.BadRequest, client.get("/api/v1/notifications/unread-count").status)
        assertEquals(HttpStatusCode.BadRequest, client.get("/api/v1/notifications?page=1&pageSize=20").status)
    }
}
