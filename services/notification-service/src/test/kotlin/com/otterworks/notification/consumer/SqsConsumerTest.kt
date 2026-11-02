package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import aws.sdk.kotlin.services.sqs.model.DeleteMessageRequest
import aws.sdk.kotlin.services.sqs.model.Message
import aws.sdk.kotlin.services.sqs.model.SendMessageRequest
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.service.NotificationService
import io.micrometer.core.instrument.simple.SimpleMeterRegistry
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.runBlocking
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
        sqsPollIntervalMs = 1000,
        sqsMaxMessages = 10,
        sqsWaitTimeSeconds = 5,
    )

    private val meterRegistry = SimpleMeterRegistry()
    private val consumer = SqsConsumer(sqsClient, notificationService, config, meterRegistry)

    private fun message(body: String?) = Message {
        messageId = "msg-1"
        receiptHandle = "rh-1"
        this.body = body
    }

    private fun counter(name: String) = meterRegistry.find(name).counter()?.count() ?: 0.0

    private val validBody = """{"eventType":"file_shared","fileId":"f-1","ownerId":"o-1","sharedWithUserId":"u-2","timestamp":"2024-01-01T00:00:00Z"}"""

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
    fun `parseMessage accepts a legacy epoch-seconds timestamp`() {
        val body = """{"eventType":"file_shared","fileId":"file-1","ownerId":"o-1","sharedWithUserId":"u-2","timestamp":1704067200}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage accepts a legacy epoch-millis timestamp`() {
        val body = """{"eventType":"file_shared","fileId":"file-1","timestamp":1704067200000}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage keeps an RFC 3339 timestamp as sent`() {
        val body = """{"eventType":"file_shared","fileId":"file-1","timestamp":"2026-10-05T15:11:33.905789+00:00"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2026-10-05T15:11:33.905789+00:00", event.timestamp)
    }

    @Test
    fun `parseMessage ignores fields the schema does not declare`() {
        val body = """{"eventType":"file_shared","fileId":"file-1","folderId":null,"unexpected":{"nested":true},"timestamp":"2024-01-01T00:00:00Z"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("file-1", event.fileId)
    }

    @Test
    fun `parseMessage accepts a full SNS envelope wrapping a legacy event`() {
        val body = """{
  "Type" : "Notification",
  "MessageId" : "30e744fd-6978-5114-a038-27c0a91e27dc",
  "TopicArn" : "arn:aws:sns:us-east-1:000000000000:otterworks-events",
  "Message" : "{\"eventType\":\"comment_added\",\"userId\":\"user-1\",\"actorId\":\"actor-1\",\"documentId\":\"doc-1\",\"commentId\":\"c-1\",\"timestamp\":1704067200}",
  "Timestamp" : "2024-01-01T00:00:01.000Z",
  "SignatureVersion" : "1",
  "Signature" : "abc==",
  "SigningCertURL" : "https://sns.us-east-1.amazonaws.com/cert.pem",
  "UnsubscribeURL" : "https://sns.us-east-1.amazonaws.com/?Action=Unsubscribe",
  "MessageAttributes" : { "source" : {"Type":"String","Value":"test"} }
}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("comment_added", event.eventType)
        assertEquals("c-1", event.commentId)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage rejects an event without eventType`() {
        assertNull(consumer.parseMessage("""{"fileId":"f","timestamp":"2024-01-01T00:00:00Z"}"""))
    }

    @Test
    fun `parseMessage rejects a timestamp that is neither string nor number`() {
        assertNull(consumer.parseMessage("""{"eventType":"file_shared","timestamp":{"epoch":1}}"""))
    }

    @Test
    fun `handleMessage processes and deletes a valid message`() = runBlocking {
        consumer.handleMessage(message(validBody))

        coVerify(exactly = 1) { notificationService.processEvent(match { it.fileId == "f-1" }) }
        coVerify(exactly = 1) { sqsClient.deleteMessage(match<DeleteMessageRequest> { it.receiptHandle == "rh-1" }) }
        coVerify(exactly = 0) { sqsClient.sendMessage(any<SendMessageRequest>()) }
        assertEquals(0.0, counter("notifications.processing.errors"))
    }

    @Test
    fun `handleMessage deletes an unparseable message instead of leaving it to be redelivered`() = runBlocking {
        consumer.handleMessage(message("not json at all"))

        coVerify(exactly = 0) { notificationService.processEvent(any()) }
        coVerify(exactly = 1) { sqsClient.deleteMessage(match<DeleteMessageRequest> { it.receiptHandle == "rh-1" }) }
        coVerify(exactly = 0) { sqsClient.sendMessage(any<SendMessageRequest>()) }
        assertEquals(1.0, counter("notifications.processing.errors"))
        assertEquals(1.0, counter("notifications.messages.deadlettered"))
    }

    @Test
    fun `handleMessage forwards an unparseable message to the dead-letter queue when configured`() = runBlocking {
        val dlqUrl = "http://localhost:4566/000000000000/test-queue-dlq"
        val consumerWithDlq = SqsConsumer(
            sqsClient,
            notificationService,
            config.copy(sqsDeadLetterQueueUrl = dlqUrl),
            meterRegistry,
        )
        val sent = slot<SendMessageRequest>()
        coEvery { sqsClient.sendMessage(capture(sent)) } returns mockk(relaxed = true)

        consumerWithDlq.handleMessage(message("""{"eventType":"file_shared","timestamp":{"bad":true}}"""))

        assertEquals(dlqUrl, sent.captured.queueUrl)
        assertEquals("""{"eventType":"file_shared","timestamp":{"bad":true}}""", sent.captured.messageBody)
        assertEquals("deserialization failed", sent.captured.messageAttributes?.get("failureReason")?.stringValue)
        assertEquals("msg-1", sent.captured.messageAttributes?.get("sourceMessageId")?.stringValue)
        coVerify(exactly = 1) { sqsClient.deleteMessage(match<DeleteMessageRequest> { it.receiptHandle == "rh-1" }) }
        coVerify(exactly = 0) { notificationService.processEvent(any()) }
    }

    @Test
    fun `handleMessage keeps the message in the queue when the dead-letter forward fails`() = runBlocking {
        val consumerWithDlq = SqsConsumer(
            sqsClient,
            notificationService,
            config.copy(sqsDeadLetterQueueUrl = "http://localhost:4566/000000000000/test-queue-dlq"),
            meterRegistry,
        )
        coEvery { sqsClient.sendMessage(any<SendMessageRequest>()) } throws RuntimeException("sqs unavailable")

        assertFailsWith<RuntimeException> { consumerWithDlq.handleMessage(message("not json at all")) }

        coVerify(exactly = 0) { sqsClient.deleteMessage(any<DeleteMessageRequest>()) }
    }

    @Test
    fun `handleMessage leaves a message for redelivery when downstream processing fails`() = runBlocking {
        coEvery { notificationService.processEvent(any()) } throws RuntimeException("dynamodb unavailable")

        assertFailsWith<RuntimeException> { consumer.handleMessage(message(validBody)) }

        coVerify(exactly = 0) { sqsClient.deleteMessage(any<DeleteMessageRequest>()) }
        coVerify(exactly = 0) { sqsClient.sendMessage(any<SendMessageRequest>()) }
        assertEquals(0.0, counter("notifications.messages.deadlettered"))
    }
}
