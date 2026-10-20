package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import aws.sdk.kotlin.services.sqs.model.Message
import aws.sdk.kotlin.services.sqs.model.ReceiveMessageResponse
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.model.EventTimestampSerializer
import com.otterworks.notification.model.SqsNotificationMessage
import com.otterworks.notification.service.NotificationService
import io.micrometer.core.instrument.simple.SimpleMeterRegistry
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
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
        sqsPollIntervalMs = 10,
        sqsMaxMessages = 10,
        sqsWaitTimeSeconds = 5,
    )

    private val consumer = SqsConsumer(sqsClient, notificationService, config)

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
        val body = """{"eventType":"file_shared","fileId":"file-123","ownerId":"owner-1","sharedWithUserId":"user-2","timestamp":1704067200}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("file_shared", event.eventType)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage accepts legacy epoch-millis timestamp inside SNS envelope`() {
        val innerMessage = """{"eventType":"comment_added","userId":"user-1","actorId":"actor-1","documentId":"doc-1","commentId":"c-1","timestamp":1718447400000}"""
        val escapedInner = innerMessage.replace("\"", "\\\"")
        val body = """{"Type":"Notification","MessageId":"msg-1","TopicArn":"arn:aws:sns:us-east-1:000000000000:test-topic","Message":"$escapedInner"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("comment_added", event.eventType)
        assertEquals("2024-06-15T10:30:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage returns null when timestamp is neither string nor integer`() {
        val body = """{"eventType":"file_shared","timestamp":{"seconds":1704067200}}"""
        assertNull(consumer.parseMessage(body))

        val bodyWithDecimal = """{"eventType":"file_shared","timestamp":1704067200.5}"""
        assertNull(consumer.parseMessage(bodyWithDecimal))
    }

    @Test
    fun `strict parser keeps the date-time contract and rejects epoch timestamps`() {
        val strict = Json { ignoreUnknownKeys = false; isLenient = false }
        val lenient = Json { ignoreUnknownKeys = true; isLenient = true }
        val epochBody = """{"eventType":"file_shared","timestamp":1704067200}"""
        val stringBody = """{"eventType":"file_shared","timestamp":"2024-01-01T00:00:00Z"}"""

        assertFailsWith<SerializationException> { strict.decodeFromString<SqsNotificationMessage>(epochBody) }
        assertEquals("2024-01-01T00:00:00Z", strict.decodeFromString<SqsNotificationMessage>(stringBody).timestamp)
        assertEquals("2024-01-01T00:00:00Z", lenient.decodeFromString<SqsNotificationMessage>(epochBody).timestamp)
    }

    @Test
    fun `fromEpoch distinguishes seconds from milliseconds`() {
        assertEquals("2024-01-01T00:00:00Z", EventTimestampSerializer.fromEpoch(1_704_067_200L))
        assertEquals("2024-01-01T00:00:00Z", EventTimestampSerializer.fromEpoch(1_704_067_200_000L))
    }

    @Test
    fun `startPolling deletes processed messages and leaves unparseable ones for the redrive policy`() = runBlocking {
        val registry = SimpleMeterRegistry()
        val polledConsumer = SqsConsumer(sqsClient, notificationService, config, registry)
        val good = Message {
            messageId = "good"
            receiptHandle = "rh-good"
            body = """{"eventType":"file_shared","fileId":"f-1","ownerId":"o-1","sharedWithUserId":"u-2","timestamp":1704067200}"""
        }
        val poison = Message {
            messageId = "poison"
            receiptHandle = "rh-poison"
            body = "not json at all"
        }
        coEvery { sqsClient.receiveMessage(any()) } returns
            ReceiveMessageResponse { messages = listOf(good, poison) } andThen
            ReceiveMessageResponse { messages = emptyList() }

        withTimeoutOrNull(500) { polledConsumer.startPolling() }

        coVerify(exactly = 1) { notificationService.processEvent(match { it.fileId == "f-1" && it.timestamp == "2024-01-01T00:00:00Z" }) }
        coVerify(exactly = 1) { sqsClient.deleteMessage(match { it.receiptHandle == "rh-good" }) }
        coVerify(exactly = 0) { sqsClient.deleteMessage(match { it.receiptHandle == "rh-poison" }) }
        assertEquals(1.0, registry.counter("notifications.processing.errors").count())
    }
}
