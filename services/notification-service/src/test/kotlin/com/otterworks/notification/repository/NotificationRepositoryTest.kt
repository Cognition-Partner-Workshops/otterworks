package com.otterworks.notification.repository

import aws.sdk.kotlin.services.dynamodb.DynamoDbClient
import aws.sdk.kotlin.services.dynamodb.model.AttributeValue
import aws.sdk.kotlin.services.dynamodb.model.ConditionalCheckFailedException
import aws.sdk.kotlin.services.dynamodb.model.PutItemRequest
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.model.Notification
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class NotificationRepositoryTest {

    private val dynamoDbClient = mockk<DynamoDbClient>(relaxed = true)
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
    private val repository = NotificationRepository(dynamoDbClient, config)

    private val notification = Notification(
        id = "n-1",
        userId = "user-1",
        type = "file_shared",
        title = "t",
        message = "m",
        createdAt = "2024-01-01T00:00:00Z",
    )

    @Test
    fun `createNotificationIfAbsent uses attribute_not_exists condition`() = runTest {
        val request = slot<PutItemRequest>()
        coEvery { dynamoDbClient.putItem(capture(request)) } returns mockk(relaxed = true)

        assertTrue(repository.createNotificationIfAbsent(notification))

        assertEquals("attribute_not_exists(id)", request.captured.conditionExpression)
        assertEquals("test-notifications", request.captured.tableName)
        assertEquals(AttributeValue.S("n-1"), request.captured.item?.get("id"))
    }

    @Test
    fun `createNotificationIfAbsent returns false when the item already exists`() = runTest {
        coEvery { dynamoDbClient.putItem(any()) } throws ConditionalCheckFailedException { message = "The conditional request failed" }

        assertFalse(repository.createNotificationIfAbsent(notification))
    }

    @Test
    fun `saveNotification stays an unconditional overwrite`() = runTest {
        val request = slot<PutItemRequest>()
        coEvery { dynamoDbClient.putItem(capture(request)) } returns mockk(relaxed = true)

        repository.saveNotification(notification)

        coVerify(exactly = 1) { dynamoDbClient.putItem(any()) }
        assertNull(request.captured.conditionExpression)
    }
}
