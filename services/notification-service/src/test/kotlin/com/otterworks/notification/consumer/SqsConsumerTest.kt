package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import aws.sdk.kotlin.services.sqs.model.DeleteMessageRequest
import aws.sdk.kotlin.services.sqs.model.Message
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.model.SqsNotificationMessage
import com.otterworks.notification.service.NotificationService
import io.micrometer.core.instrument.simple.SimpleMeterRegistry
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.test.runTest
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
        val body = """
            {
                "eventType": "file_shared",
                "fileId": "file-123",
                "ownerId": "owner-1",
                "sharedWithUserId": "user-2",
                "timestamp": 1704067200
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("file_shared", event.eventType)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage accepts legacy epoch-millis timestamp`() {
        val body = """{"eventType":"document_edited","userId":"user-1","documentId":"doc-1","timestamp":1704067200123}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-01-01T00:00:00.123Z", event.timestamp)
    }

    @Test
    fun `parseMessage accepts SNS-wrapped legacy epoch timestamp`() {
        val innerMessage = """{"eventType":"comment_added","userId":"user-1","actorId":"actor-1","documentId":"doc-1","commentId":"c-1","timestamp":1704067200}"""
        val escapedInner = innerMessage.replace("\"", "\\\"")
        val body = """{"Type":"Notification","MessageId":"msg-1","TopicArn":"arn:aws:sns:us-east-1:000000000000:test-topic","Message":"$escapedInner"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("comment_added", event.eventType)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage ignores fields it does not know about`() {
        val body = """{"eventType":"file_shared","sharedWithUserId":"user-2","timestamp":"2024-01-01T00:00:00Z","schemaVersion":2,"source":"legacy-portal"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("user-2", event.sharedWithUserId)
    }

    @Test
    fun `parseMessage rejects non-primitive timestamp`() {
        val body = """{"eventType":"file_shared","timestamp":{"seconds":1704067200}}"""

        assertNull(consumer.parseMessage(body))
    }

    @Test
    fun `handleMessage processes and deletes a legacy message`() = runTest {
        val msg = Message {
            messageId = "m-1"
            receiptHandle = "rh-1"
            body = """{"eventType":"file_shared","fileId":"f-1","ownerId":"o-1","sharedWithUserId":"u-1","timestamp":1704067200}"""
        }
        val processed = slot<SqsNotificationMessage>()
        coEvery { notificationService.processEvent(capture(processed)) } returns Unit

        consumer.handleMessage(msg)

        assertEquals("2024-01-01T00:00:00Z", processed.captured.timestamp)
        coVerify(exactly = 1) { sqsClient.deleteMessage(match<DeleteMessageRequest> { it.receiptHandle == "rh-1" }) }
        assertEquals(0.0, meterRegistry.counter("notifications.processing.errors").count())
    }

    @Test
    fun `handleMessage counts and deletes a malformed message instead of leaving it to re-queue`() = runTest {
        val msg = Message {
            messageId = "m-2"
            receiptHandle = "rh-2"
            body = "not json at all"
        }

        consumer.handleMessage(msg)

        coVerify(exactly = 0) { notificationService.processEvent(any()) }
        coVerify(exactly = 1) { sqsClient.deleteMessage(match<DeleteMessageRequest> { it.receiptHandle == "rh-2" }) }
        assertEquals(1.0, meterRegistry.counter("notifications.processing.errors").count())
        assertEquals(1.0, meterRegistry.counter("notifications.messages.malformed").count())
    }

    @Test
    fun `handleMessage leaves a message in the queue when processing fails transiently`() = runTest {
        val msg = Message {
            messageId = "m-3"
            receiptHandle = "rh-3"
            body = """{"eventType":"file_shared","sharedWithUserId":"u-1","timestamp":"2024-01-01T00:00:00Z"}"""
        }
        coEvery { notificationService.processEvent(any()) } throws IllegalStateException("dynamodb unavailable")

        consumer.handleMessage(msg)

        coVerify(exactly = 0) { sqsClient.deleteMessage(any<DeleteMessageRequest>()) }
        assertEquals(1.0, meterRegistry.counter("notifications.processing.errors").count())
    }
}
