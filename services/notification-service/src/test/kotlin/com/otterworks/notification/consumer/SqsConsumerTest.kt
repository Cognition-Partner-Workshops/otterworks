package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import aws.sdk.kotlin.services.sqs.model.DeleteMessageRequest
import aws.sdk.kotlin.services.sqs.model.Message
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.service.NotificationService
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import io.mockk.slot
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
        sqsMaxReceiveCount = 3,
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
    fun `parseMessage accepts legacy epoch-milliseconds timestamp`() {
        val body = """{"eventType":"document_edited","userId":"user-1","documentId":"doc-1","timestamp":1704067200000}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage normalises quoted epoch timestamp`() {
        val body = """{"eventType":"document_edited","userId":"user-1","documentId":"doc-1","timestamp":"1704067200"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage keeps RFC 3339 timestamp as sent`() {
        val body = """{"eventType":"document_edited","userId":"user-1","documentId":"doc-1","timestamp":"2024-06-15T10:30:00+02:00"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("2024-06-15T10:30:00+02:00", event.timestamp)
    }

    @Test
    fun `parseMessage accepts SNS envelope with epoch timestamp and undeclared envelope fields`() {
        val innerMessage = """{"eventType":"comment_added","userId":"user-1","actorId":"actor-1","documentId":"doc-1","commentId":"c-1","timestamp":1704067200}"""
        val escapedInner = innerMessage.replace("\"", "\\\"")
        val body = """
            {
                "Type": "Notification",
                "MessageId": "msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:000000000000:test-topic",
                "Timestamp": "2024-01-01T00:00:00.000Z",
                "SignatureVersion": "1",
                "Signature": "abc",
                "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
                "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/unsubscribe",
                "Message": "$escapedInner"
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("comment_added", event.eventType)
        assertEquals("2024-01-01T00:00:00Z", event.timestamp)
    }

    @Test
    fun `parseMessage ignores fields the schema does not declare`() {
        val body = """{"eventType":"file_shared","fileId":"file-123","sharedWithUserId":"user-2","sourceService":"file-service","timestamp":"2024-01-01T00:00:00Z"}"""

        val event = consumer.parseMessage(body)

        assertNotNull(event)
        assertEquals("file-123", event.fileId)
    }

    @Test
    fun `handleMessage processes and deletes a legacy message`() = runBlocking {
        val msg = Message {
            messageId = "m-1"
            receiptHandle = "rh-1"
            body = """{"eventType":"file_shared","fileId":"file-1","ownerId":"o-1","sharedWithUserId":"u-2","timestamp":1704067200}"""
            attributes = mapOf(RECEIVE_COUNT_ATTRIBUTE to "1")
        }

        consumer.handleMessage(msg)

        coVerify(exactly = 1) { notificationService.processEvent(match { it.fileId == "file-1" }) }
        val delete = slot<DeleteMessageRequest>()
        coVerify(exactly = 1) { sqsClient.deleteMessage(capture(delete)) }
        assertEquals("rh-1", delete.captured.receiptHandle)
    }

    @Test
    fun `handleMessage leaves an unparseable message for the redrive policy while under the receive limit`() = runBlocking {
        val msg = Message {
            messageId = "m-2"
            receiptHandle = "rh-2"
            body = "not json at all"
            attributes = mapOf(RECEIVE_COUNT_ATTRIBUTE to "3")
        }

        consumer.handleMessage(msg)

        coVerify(exactly = 0) { notificationService.processEvent(any()) }
        coVerify(exactly = 0) { sqsClient.deleteMessage(any()) }
    }

    @Test
    fun `handleMessage discards an unparseable message once it has outlived the redrive limit`() = runBlocking {
        val msg = Message {
            messageId = "m-3"
            receiptHandle = "rh-3"
            body = "not json at all"
            attributes = mapOf(RECEIVE_COUNT_ATTRIBUTE to "4")
        }

        consumer.handleMessage(msg)

        coVerify(exactly = 0) { notificationService.processEvent(any()) }
        val delete = slot<DeleteMessageRequest>()
        coVerify(exactly = 1) { sqsClient.deleteMessage(capture(delete)) }
        assertEquals("rh-3", delete.captured.receiptHandle)
    }

    @Test
    fun `handleMessage keeps the message when processing fails so it is redelivered`() = runBlocking {
        coEvery { notificationService.processEvent(any()) } throws IllegalStateException("dynamo down")
        val msg = Message {
            messageId = "m-4"
            receiptHandle = "rh-4"
            body = """{"eventType":"file_shared","fileId":"file-1","sharedWithUserId":"u-2","timestamp":"2024-01-01T00:00:00Z"}"""
        }

        consumer.handleMessage(msg)

        coVerify(exactly = 0) { sqsClient.deleteMessage(any()) }
    }
}
