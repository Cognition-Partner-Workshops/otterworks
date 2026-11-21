package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import aws.sdk.kotlin.services.sqs.model.DeleteMessageRequest
import aws.sdk.kotlin.services.sqs.model.Message
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.service.NotificationService
import io.micrometer.core.instrument.simple.SimpleMeterRegistry
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class SqsConsumerTest {

    private val sqsClient = mockk<SqsClient>(relaxed = true)
    private val notificationService = mockk<NotificationService>(relaxed = true)
    private val config = AppConfig(
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
    )

    private val meterRegistry = SimpleMeterRegistry()
    private val consumer = SqsConsumer(sqsClient, notificationService, config, meterRegistry)

    private fun message(id: String, body: String?) = Message {
        messageId = id
        receiptHandle = "rh-$id"
        this.body = body
    }

    private fun counter(name: String) = meterRegistry.find(name).counter()?.count() ?: 0.0

    @Test
    fun `parseMessage parses direct SQS message`() {
        val body = """
            {
                "eventType": "file_shared",
                "fileId": "file-123",
                "ownerId": "owner-1",
                "sharedWithUserId": "user-2",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("file_shared", event.eventType)
        assertEquals("file-123", event.fileId)
        assertEquals("owner-1", event.ownerId)
        assertEquals("user-2", event.sharedWithUserId)
    }

    @Test
    fun `parseMessage parses SNS-wrapped message`() {
        val innerMessage = """{"eventType":"comment_added","userId":"user-1","actorId":"actor-1","documentId":"doc-1","commentId":"c-1","timestamp":"2024-01-01T00:00:00Z"}"""
        val escapedInner = innerMessage.replace("\"", "\\\"")
        val body = """
            {
                "Type": "Notification",
                "MessageId": "msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:000000000000:test-topic",
                "Message": "$escapedInner"
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("comment_added", event.eventType)
        assertEquals("user-1", event.userId)
        assertEquals("actor-1", event.actorId)
        assertEquals("doc-1", event.documentId)
        assertEquals("c-1", event.commentId)
    }

    @Test
    fun `parseMessage returns null for invalid JSON`() {
        val event = consumer.parseMessage("not json at all")
        assertNull(event)
    }

    @Test
    fun `parseMessage parses document_edited event`() {
        val body = """
            {
                "eventType": "document_edited",
                "userId": "user-1",
                "actorId": "editor-1",
                "documentId": "doc-456",
                "timestamp": "2024-06-15T10:30:00Z"
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("document_edited", event.eventType)
        assertEquals("doc-456", event.documentId)
        assertEquals("editor-1", event.actorId)
    }

    @Test
    fun `parseMessage parses user_mentioned event`() {
        val body = """
            {
                "eventType": "user_mentioned",
                "mentionedUserId": "mentioned-user",
                "actorId": "actor-2",
                "documentId": "doc-789",
                "timestamp": "2024-06-15T10:30:00Z"
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("user_mentioned", event.eventType)
        assertEquals("mentioned-user", event.mentionedUserId)
        assertEquals("actor-2", event.actorId)
        assertEquals("doc-789", event.documentId)
    }

    @Test
    fun `parseMessage handles missing optional fields`() {
        val body = """
            {
                "eventType": "file_shared",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("file_shared", event.eventType)
        assertEquals("", event.fileId)
        assertEquals("", event.ownerId)
        assertEquals("", event.sharedWithUserId)
    }

    @Test
    fun `parseMessage accepts legacy epoch-seconds timestamp`() {
        val body = """{"eventType":"file_shared","fileId":"file-1","timestamp":1704067200}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage accepts legacy epoch-millis timestamp`() {
        val body = """{"eventType":"file_shared","fileId":"file-1","timestamp":1704067200123}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-01-01T00:00:00.123Z", event.timestamp)
    }

    @Test
    fun `parseMessage accepts epoch timestamp inside SNS envelope with extra keys`() {
        val innerMessage = """{"eventType":"comment_added","userId":"user-1","documentId":"doc-1","timestamp":1718447400}"""
        val escapedInner = innerMessage.replace("\"", "\\\"")
        val body = """
            {
                "Type": "Notification",
                "MessageId": "msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:000000000000:test-topic",
                "Timestamp": "2024-06-15T10:30:00.000Z",
                "SignatureVersion": "1",
                "Signature": "abc",
                "Message": "$escapedInner"
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("comment_added", event.eventType)
        assertEquals("2024-06-15T10:30:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage preserves RFC 3339 timestamps unchanged`() {
        val body = """{"eventType":"file_shared","timestamp":"2024-06-15T10:30:00+02:00"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-06-15T10:30:00+02:00", event.timestamp)
    }

    @Test
    fun `handleMessage processes and deletes a valid message`() = runBlocking {
        val msg = message("m-1", """{"eventType":"file_shared","fileId":"f","timestamp":1704067200}""")

        consumer.handleMessage(msg)

        coVerify(exactly = 1) { notificationService.processEvent(match { it.fileId == "f" }) }
        coVerify(exactly = 1) { sqsClient.deleteMessage(match<DeleteMessageRequest> { it.receiptHandle == "rh-m-1" }) }
        assertEquals(0.0, counter("notifications.processing.errors"))
    }

    @Test
    fun `handleMessage deletes an unparseable message instead of leaving it to redeliver`() = runBlocking {
        val msg = message("m-2", "not json at all")

        consumer.handleMessage(msg)

        coVerify(exactly = 0) { notificationService.processEvent(any()) }
        coVerify(exactly = 1) { sqsClient.deleteMessage(match<DeleteMessageRequest> { it.receiptHandle == "rh-m-2" }) }
        assertEquals(1.0, counter("notifications.processing.errors"))
        assertEquals(1.0, counter("notifications.poison.messages"))
    }

    @Test
    fun `handleMessage leaves the message on the queue when processing fails`() = runBlocking {
        coEvery { notificationService.processEvent(any()) } throws IllegalStateException("downstream unavailable")
        val msg = message("m-3", """{"eventType":"file_shared","fileId":"f","timestamp":"2024-01-01T00:00:00Z"}""")

        consumer.handleMessage(msg)

        coVerify(exactly = 0) { sqsClient.deleteMessage(any<DeleteMessageRequest>()) }
        assertEquals(1.0, counter("notifications.processing.errors"))
        assertEquals(0.0, counter("notifications.poison.messages"))
    }
}
