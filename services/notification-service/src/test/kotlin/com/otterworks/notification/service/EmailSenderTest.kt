package com.otterworks.notification.service

import aws.sdk.kotlin.services.ses.SesClient
import aws.sdk.kotlin.services.ses.model.SendEmailRequest
import aws.sdk.kotlin.services.ses.model.SendEmailResponse
import com.otterworks.notification.config.AppConfig
import io.mockk.coEvery
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class EmailSenderTest {
    private val client = mockk<SesClient>()
    private val sender = EmailSender(client, AppConfig.load().copy(sesFromEmail = "sender@example.com"))

    @Test
    fun `sends customer address and unicode content using configured sender`() = runTest {
        val request = slot<SendEmailRequest>()
        coEvery { client.sendEmail(capture(request)) } returns SendEmailResponse { messageId = "sent" }
        assertTrue(sender.sendEmail("customer@example.com", "Shared résumé", "<p>Hello 世界</p>"))
        assertEquals("sender@example.com", request.captured.source)
        assertEquals(listOf("customer@example.com"), request.captured.destination?.toAddresses)
        assertEquals("Shared résumé", request.captured.message?.subject?.data)
        assertEquals("UTF-8", request.captured.message?.subject?.charset)
        assertEquals("<p>Hello 世界</p>", request.captured.message?.body?.html?.data)
        assertEquals("UTF-8", request.captured.message?.body?.html?.charset)
    }

    @Test
    fun `provider rejection returns false so notification processing can continue`() = runTest {
        coEvery { client.sendEmail(any<SendEmailRequest>()) } throws IllegalStateException("provider unavailable")
        assertFalse(sender.sendEmail("customer@example.com", "Shared file", "<p>Shared</p>"))
    }
}
