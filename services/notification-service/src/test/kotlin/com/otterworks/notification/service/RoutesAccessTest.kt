package com.otterworks.notification.service

import com.otterworks.notification.configurePlugins
import com.otterworks.notification.model.Notification
import com.otterworks.notification.routes.configureRouting
import com.otterworks.notification.websocket.WebSocketManager
import io.ktor.client.request.*
import io.ktor.http.*
import io.ktor.server.application.install
import io.ktor.server.testing.testApplication
import io.micrometer.prometheus.PrometheusConfig
import io.micrometer.prometheus.PrometheusMeterRegistry
import io.mockk.*
import org.koin.dsl.module
import org.koin.ktor.plugin.Koin
import kotlin.test.Test
import kotlin.test.assertEquals

class RoutesAccessTest {
    @Test
    fun `routes reject anonymous and foreign notification access and ignore body identity`() = testApplication {
        val service = mockk<NotificationService>(relaxed = true)
        val sockets = mockk<WebSocketManager>(relaxed = true)
        coEvery { service.getNotificationById("private") } returns Notification(
            id = "private", userId = "owner", type = "file_shared", title = "Private", message = "secret", createdAt = "2024-01-01")
        application {
            configurePlugins()
            install(Koin) { modules(module { single { service }; single { sockets } }) }
            configureRouting(PrometheusMeterRegistry(PrometheusConfig.DEFAULT))
        }
        assertEquals(HttpStatusCode.NotFound, client.get("/api/v1/notifications/private") { header("X-User-ID", "other") }.status)
        assertEquals(HttpStatusCode.Unauthorized, client.get("/api/v1/notifications?user_id=owner").status)
        assertEquals(HttpStatusCode.Unauthorized, client.get("/api/v1/preferences?user_id=owner").status)
        assertEquals(HttpStatusCode.OK, client.get("/api/v1/notifications/private") { header("X-User-ID", "owner") }.status)
        assertEquals(HttpStatusCode.NotFound, client.put("/api/v1/notifications/private/read") { header("X-User-ID", "other") }.status)
        assertEquals(HttpStatusCode.NotFound, client.delete("/api/v1/notifications/private") { header("X-User-ID", "other") }.status)
        assertEquals(HttpStatusCode.NoContent, client.put("/api/v1/preferences") {
            header("X-User-ID", "caller")
            contentType(ContentType.Application.Json)
            setBody("""{"userId":"victim","eventType":"file_shared","channels":[]}""")
        }.status)
        coVerify(exactly = 1) { service.updatePreferences("caller", "file_shared", emptyList()) }
        coVerify(exactly = 0) { service.markAsRead(any()) }
        coVerify(exactly = 0) { service.deleteNotification(any()) }
    }
}
