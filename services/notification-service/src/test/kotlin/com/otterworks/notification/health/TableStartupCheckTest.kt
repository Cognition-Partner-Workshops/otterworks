package com.otterworks.notification.health

import aws.sdk.kotlin.services.dynamodb.DynamoDbClient
import aws.sdk.kotlin.services.dynamodb.model.DescribeTableRequest
import aws.sdk.kotlin.services.dynamodb.model.DescribeTableResponse
import aws.sdk.kotlin.services.dynamodb.model.ResourceNotFoundException
import aws.sdk.kotlin.services.dynamodb.model.TableDescription
import aws.sdk.kotlin.services.dynamodb.model.TableStatus
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class TableStartupCheckTest {

    private val dynamoDbClient = mockk<DynamoDbClient>()

    @Test
    fun `run returns false when the table is not found`() = runBlocking {
        coEvery {
            dynamoDbClient.describeTable(any<DescribeTableRequest>())
        } throws ResourceNotFoundException { message = "Requested resource not found" }

        val check = TableStartupCheck(dynamoDbClient, "test-notifications")

        assertFalse(check.run())
        assertFalse(check.isReady)
    }

    @Test
    fun `run returns true when the table exists`() = runBlocking {
        coEvery {
            dynamoDbClient.describeTable(any<DescribeTableRequest>())
        } returns DescribeTableResponse {
            table = TableDescription {
                tableName = "test-notifications"
                tableStatus = TableStatus.Active
            }
        }

        val check = TableStartupCheck(dynamoDbClient, "test-notifications")

        assertTrue(check.run())
        assertTrue(check.isReady)
    }
}
