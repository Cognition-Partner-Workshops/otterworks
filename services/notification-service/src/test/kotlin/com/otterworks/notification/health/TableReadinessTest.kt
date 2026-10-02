package com.otterworks.notification.health

import aws.sdk.kotlin.services.dynamodb.DynamoDbClient
import aws.sdk.kotlin.services.dynamodb.model.DescribeTableRequest
import aws.sdk.kotlin.services.dynamodb.model.DescribeTableResponse
import aws.sdk.kotlin.services.dynamodb.model.ResourceNotFoundException
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class TableReadinessTest {

    private val dynamoDb = mockk<DynamoDbClient>()

    @Test
    fun `check returns false when the configured table is unavailable`() = runTest {
        coEvery { dynamoDb.describeTable(any<DescribeTableRequest>()) } throws
            ResourceNotFoundException { message = "table not found" }

        val readiness = TableReadiness(dynamoDb, "missing-table")

        assertFalse(readiness.check())
        assertFalse(readiness.isReady)
    }

    @Test
    fun `check returns true when the configured table is available`() = runTest {
        coEvery { dynamoDb.describeTable(any<DescribeTableRequest>()) } returns DescribeTableResponse {}

        val readiness = TableReadiness(dynamoDb, "notifications")

        assertTrue(readiness.check())
        assertTrue(readiness.isReady)
    }
}
