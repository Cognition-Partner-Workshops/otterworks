package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.service.NotificationService
import io.mockk.mockk
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
    fun `parseMessage parses the SNS envelope from the cloud-worker DLQ`() {
        // Dead-letter body from otterworks-cw-notifications-dlq, account number replaced.
        val body = """
            {
              "Type" : "Notification",
              "MessageId" : "96475d9d-e9b3-5c35-a8aa-3ea08cb5acfc",
              "TopicArn" : "arn:aws:sns:us-east-1:<account>:otterworks-cw-events",
              "Message" : "{\"eventType\":\"file_shared\",\"fileId\":\"17c9ef4b-8fa2-4047-a66a-af973d61d67b\",\"ownerId\":\"5eed0001-0000-4000-a000-000000000001\",\"folderId\":null,\"sharedWithUserId\":\"5eed0002-0000-4000-a000-000000000002\",\"timestamp\":\"2026-10-05T08:41:41.650653+00:00\"}",
              "Timestamp" : "2026-10-05T08:41:42.315Z",
              "SignatureVersion" : "1",
              "Signature" : "AKdnFEwI/aiaQMnL+NWCQRXzW90KXdOZe5PTSCfvWeZ9qqnbf1edEZet5E7dbKracfCsSrG4+D7AbMj3xC+faMEdHRpwArbr1mJKFv00o3TCo5c6lYRQNKwKUydioNNysbbEETUDIcUy/fIN1zDFi+DZ6DYUA5eOfIoqFTIyp3ZlXkrTeIcxfggD6bADTCgOaSr0/OKDaJlS8HpAga0PqZpfjGxl/A8bv/JsYrxGlW1wFvHRQ9swlpxv5m4yL2PdqKSwJP4pwHTrx+FvGt3O5pZZjW0one2RyQzat49gg0UoA9MVXVCwjeehZxO0mG8w/b5SE+8lgPUnaEsCbbjxgA==",
              "SigningCertURL" : "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-1e59c4574facfe41babdb2d652f8ebef.pem",
              "UnsubscribeURL" : "https://sns.us-east-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:us-east-1:<account>:otterworks-cw-events:7ab97102-bb50-4a79-a944-f017b10368d6",
              "MessageAttributes" : {
                "demoSource" : {"Type":"String","Value":"aws-cloud-worker"}
              }
            }
        """.trimIndent()

        val event = consumer.parseMessage(body)
        assertNotNull(event)
        assertEquals("file_shared", event.eventType)
        assertEquals("17c9ef4b-8fa2-4047-a66a-af973d61d67b", event.fileId)
        assertEquals("5eed0001-0000-4000-a000-000000000001", event.ownerId)
        assertEquals("5eed0002-0000-4000-a000-000000000002", event.sharedWithUserId)
        assertEquals("2026-10-05T08:41:41.650653+00:00", event.timestamp)
    }

    @Test
    fun `parseMessage rejects an event without the required eventType`() {
        val body = """
            {
                "fileId": "file-123",
                "unexpectedField": "value",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        """.trimIndent()

        assertNull(consumer.parseMessage(body))
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
}
