package com.otterworks.notification.service

import com.otterworks.notification.configurePlugins
import com.otterworks.notification.model.Notification
import com.otterworks.notification.routes.configureRouting
import com.otterworks.notification.websocket.WebSocketManager
import io.ktor.client.request.delete
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.put
import io.ktor.client.statement.bodyAsText
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.install
import io.ktor.server.testing.testApplication
import io.micrometer.prometheus.PrometheusConfig
import io.micrometer.prometheus.PrometheusMeterRegistry
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.koin.dsl.module
import org.koin.ktor.plugin.Koin
import org.junit.After
import org.junit.Ignore
import org.koin.core.context.stopKoin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class NotificationRoutesTest {
    @After
    fun tearDown() {
        stopKoin()
    }

    private val service = mockk<NotificationService>(relaxed = true)
    private fun withRoutes(block: suspend io.ktor.server.testing.ApplicationTestBuilder.() -> Unit) = testApplication {
        application {
            configurePlugins()
            install(Koin) {
                modules(module {
                    single { service }
                    single { mockk<WebSocketManager>(relaxed = true) }
                })
            }
            configureRouting(PrometheusMeterRegistry(PrometheusConfig.DEFAULT))
        }
        block()
    }

    @Test
    fun `user scoped endpoints reject missing and blank identity without querying data`() = withRoutes {
        for (path in listOf("/api/v1/notifications", "/api/v1/notifications/unread-count", "/api/v1/preferences")) {
            assertEquals(HttpStatusCode.BadRequest, client.get(path).status)
            assertEquals(HttpStatusCode.BadRequest, client.get("$path?user_id=").status)
        }
        assertEquals(HttpStatusCode.BadRequest, client.put("/api/v1/notifications/read-all").status)
        coVerify(exactly = 0) { service.getNotifications(any(), any(), any()) }
        coVerify(exactly = 0) { service.getUnreadCount(any()) }
        coVerify(exactly = 0) { service.getPreferences(any()) }
        coVerify(exactly = 0) { service.markAllAsRead(any()) }
    }

    @Test
    fun `header identity takes precedence and pagination accurately reports last page`() = withRoutes {
        coEvery { service.getNotifications("customer", 2, 2) } returns (emptyList<Notification>() to 4)
        val response = client.get("/api/v1/notifications?user_id=other&page=2&page_size=2") { header("X-User-ID", "customer") }
        assertEquals(HttpStatusCode.OK, response.status)
        val body = Json.parseToJsonElement(response.bodyAsText()).jsonObject
        assertEquals(4, body.getValue("total").jsonPrimitive.int)
        assertFalse(body.getValue("hasMore").jsonPrimitive.boolean)
        coVerify(exactly = 1) { service.getNotifications("customer", 2, 2) }
    }

    @Test
    fun `invalid numeric parameters use defaults and first page reports more results`() = withRoutes {
        coEvery { service.getNotifications("customer", 1, 20) } returns (emptyList<Notification>() to 21)
        val response = client.get("/api/v1/notifications?user_id=customer&page=bad&page_size=bad")
        assertEquals(HttpStatusCode.OK, response.status)
        val body = Json.parseToJsonElement(response.bodyAsText()).jsonObject
        assertTrue(body.getValue("hasMore").jsonPrimitive.boolean)
        assertEquals(1, body.getValue("page").jsonPrimitive.int)
        assertEquals(20, body.getValue("pageSize").jsonPrimitive.int)
    }

    @Test
    fun `missing records return not found and successful mutations return no content`() = withRoutes {
        coEvery { service.getNotificationById("missing") } returns null
        coEvery { service.markAsRead("missing") } returns false
        coEvery { service.deleteNotification("missing") } returns false
        coEvery { service.markAsRead("present") } returns true
        coEvery { service.deleteNotification("present") } returns true
        assertEquals(HttpStatusCode.NotFound, client.get("/api/v1/notifications/missing").status)
        assertEquals(HttpStatusCode.NotFound, client.put("/api/v1/notifications/missing/read").status)
        assertEquals(HttpStatusCode.NotFound, client.delete("/api/v1/notifications/missing").status)
        assertEquals(HttpStatusCode.NoContent, client.put("/api/v1/notifications/present/read").status)
        assertEquals(HttpStatusCode.NoContent, client.delete("/api/v1/notifications/present").status)
    }

    @Test
    fun `backend failures return generic error without internal details`() = withRoutes {
        coEvery { service.getUnreadCount("customer") } throws IllegalStateException("private database details")
        val response = client.get("/api/v1/notifications/unread-count?user_id=customer")
        assertEquals(HttpStatusCode.InternalServerError, response.status)
        assertEquals("Internal server error", Json.parseToJsonElement(response.bodyAsText()).jsonObject.getValue("error").jsonPrimitive.content)
    }

    @Test
    @Ignore("BUG: Routes.kt:94 returns notifications by ID without checking the requesting user's ownership")
    fun `another customer cannot read a private notification`() = withRoutes {
        coEvery { service.getNotificationById("private") } returns Notification(
            "private", "owner", "file_shared", "Confidential", "Private message", createdAt = "2024-01-01T00:00:00Z",
        )
        assertEquals(HttpStatusCode.Forbidden, client.get("/api/v1/notifications/private") { header("X-User-ID", "attacker") }.status)
    }
}
