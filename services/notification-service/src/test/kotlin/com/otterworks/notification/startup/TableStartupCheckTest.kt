package com.otterworks.notification.startup

import aws.sdk.kotlin.services.dynamodb.DynamoDbClient
import aws.sdk.kotlin.services.dynamodb.model.DescribeTableRequest
import aws.sdk.kotlin.services.dynamodb.model.DescribeTableResponse
import aws.sdk.kotlin.services.dynamodb.model.ResourceNotFoundException
import com.otterworks.notification.config.AppConfig
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class TableStartupCheckTest {

    private val dynamoDbClient = mockk<DynamoDbClient>()
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

    @Test
    fun `run returns false and stays not ready when the table is missing`() = runTest {
        coEvery { dynamoDbClient.describeTable(any<DescribeTableRequest>()) } throws
            ResourceNotFoundException { message = "Requested resource not found" }

        val check = TableStartupCheck(dynamoDbClient, config)

        assertFalse(check.run())
        assertFalse(check.isReady)
    }

    @Test
    fun `run returns true and marks ready when the table exists`() = runTest {
        coEvery { dynamoDbClient.describeTable(any<DescribeTableRequest>()) } returns
            DescribeTableResponse { }

        val check = TableStartupCheck(dynamoDbClient, config)

        assertTrue(check.run())
        assertTrue(check.isReady)
    }
}
