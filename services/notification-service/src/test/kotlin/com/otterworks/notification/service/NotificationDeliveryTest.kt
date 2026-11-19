package com.otterworks.notification.service

import com.otterworks.notification.model.DeliveryChannel
import com.otterworks.notification.model.Notification
import com.otterworks.notification.model.NotificationPreference
import com.otterworks.notification.model.SqsNotificationMessage
import com.otterworks.notification.repository.NotificationRepository
import com.otterworks.notification.websocket.WebSocketManager
import io.micrometer.core.instrument.simple.SimpleMeterRegistry
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.coVerifyOrder
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class NotificationDeliveryTest {
    private val repository = mockk<NotificationRepository>(relaxed = true)
    private val email = mockk<EmailSender>()
    private val sockets = mockk<WebSocketManager>()
    private val metrics = SimpleMeterRegistry()
    private val service = NotificationService(repository, email, sockets, metrics)
    private val event = SqsNotificationMessage(
        eventType = "file_shared", sharedWithUserId = "recipient", ownerId = "owner",
        fileId = "file", timestamp = "2024-01-01T00:00:00Z",
    )

    @Test
    fun `offline push and rejected email still preserve in app notification`() = runTest {
        coEvery { repository.getPreferences("recipient") } returns NotificationPreference("recipient")
        coEvery { email.sendEmail(any(), any(), any()) } returns false
        coEvery { sockets.pushNotification("recipient", any()) } returns 0
        val saved = mutableListOf<Notification>()
        coEvery { repository.saveNotification(capture(saved)) } returns Unit

        service.processEvent(event)

        assertEquals(1, saved.size)
        assertEquals(listOf("in_app"), saved.single().deliveredVia)
        assertEquals("owner", saved.single().actorId)
        assertEquals("file", saved.single().resourceId)
        assertEquals(false, saved.single().read)
        assertEquals(1.0, metrics.counter("notifications.processed").count())
        assertEquals(0.0, metrics.counter("notifications.email.sent").count())
        assertEquals(0.0, metrics.counter("notifications.push.sent").count())
    }

    @Test
    fun `successful delivery records channels and counts push once for multiple sessions`() = runTest {
        coEvery { repository.getPreferences("recipient") } returns NotificationPreference("recipient")
        coEvery { email.sendEmail("recipient@otterworks.io", any(), any()) } returns true
        coEvery { sockets.pushNotification("recipient", any()) } returns 3
        val saved = mutableListOf<Notification>()
        coEvery { repository.saveNotification(any()) } answers {
            saved.add(firstArg<Notification>().copy(deliveredVia = firstArg<Notification>().deliveredVia.toList()))
        }

        service.processEvent(event)

        assertEquals(listOf("in_app", "email"), saved.first().deliveredVia)
        assertEquals(listOf("in_app", "email", "push"), saved.last().deliveredVia)
        assertEquals(saved.first().id, saved.last().id)
        assertEquals(1.0, metrics.counter("notifications.email.sent").count())
        assertEquals(1.0, metrics.counter("notifications.push.sent").count())
        coVerifyOrder {
            repository.saveNotification(any())
            sockets.pushNotification("recipient", any())
            repository.saveNotification(any())
        }
    }

    @Test
    fun `empty channel preference suppresses external delivery`() = runTest {
        coEvery { repository.getPreferences("recipient") } returns NotificationPreference(
            "recipient", mapOf("file_shared" to emptyList()),
        )
        service.processEvent(event)
        coVerify { repository.saveNotification(match { it.deliveredVia.isEmpty() }) }
        coVerify(exactly = 0) { email.sendEmail(any(), any(), any()) }
        coVerify(exactly = 0) { sockets.pushNotification(any(), any()) }
    }

    @Test
    fun `storage failure propagates without sending push or counting completion`() = runTest {
        coEvery { repository.getPreferences("recipient") } returns NotificationPreference(
            "recipient", mapOf("file_shared" to listOf(DeliveryChannel.IN_APP, DeliveryChannel.PUSH)),
        )
        coEvery { repository.saveNotification(any()) } throws IllegalStateException("unavailable")
        assertFailsWith<IllegalStateException> { service.processEvent(event) }
        coVerify(exactly = 0) { sockets.pushNotification(any(), any()) }
        assertEquals(0.0, metrics.counter("notifications.processed").count())
    }

    @Test
    fun `updating one event preference preserves other event choices`() = runTest {
        val original = NotificationPreference("recipient")
        coEvery { repository.getPreferences("recipient") } returns original
        service.updatePreferences("recipient", "file_shared", emptyList())
        coVerify {
            repository.savePreferences(match {
                it.userId == "recipient" && it.channels["file_shared"] == emptyList<DeliveryChannel>() &&
                    it.channels.filterKeys { key -> key != "file_shared" } == original.channels.filterKeys { key -> key != "file_shared" }
            })
        }
    }
}
