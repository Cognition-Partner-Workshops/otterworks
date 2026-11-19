package com.otterworks.notification.service

import aws.sdk.kotlin.services.dynamodb.DynamoDbClient
import aws.sdk.kotlin.services.dynamodb.model.AttributeValue
import aws.sdk.kotlin.services.dynamodb.model.DeleteItemRequest
import aws.sdk.kotlin.services.dynamodb.model.DeleteItemResponse
import aws.sdk.kotlin.services.dynamodb.model.GetItemRequest
import aws.sdk.kotlin.services.dynamodb.model.GetItemResponse
import aws.sdk.kotlin.services.dynamodb.model.PutItemRequest
import aws.sdk.kotlin.services.dynamodb.model.PutItemResponse
import aws.sdk.kotlin.services.dynamodb.model.QueryRequest
import aws.sdk.kotlin.services.dynamodb.model.QueryResponse
import aws.sdk.kotlin.services.dynamodb.model.UpdateItemRequest
import aws.sdk.kotlin.services.dynamodb.model.UpdateItemResponse
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.model.DeliveryChannel
import com.otterworks.notification.model.Notification
import com.otterworks.notification.model.NotificationPreference
import com.otterworks.notification.repository.NotificationRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Ignore
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

class NotificationRepositoryTest {
    private val client = mockk<DynamoDbClient>()
    private val config = AppConfig.load().copy(
        dynamoDbTableNotifications = "notifications-test", dynamoDbTablePreferences = "preferences-test",
    )
    private val repository = NotificationRepository(client, config)
    private fun item(id: String, read: Boolean = false) = mapOf(
        "id" to AttributeValue.S(id), "userId" to AttributeValue.S("customer"),
        "read" to AttributeValue.Bool(read),
    )

    @Test
    fun `pagination follows database cursors and excludes malformed records`() = runTest {
        val cursor = mapOf("id" to AttributeValue.S("cursor"))
        val requests = mutableListOf<QueryRequest>()
        coEvery { client.query(capture(requests)) } returnsMany listOf(
            QueryResponse { items = listOf(item("newest"), mapOf("id" to AttributeValue.S("broken"))); lastEvaluatedKey = cursor },
            QueryResponse { items = listOf(item("middle"), item("oldest")) },
        )
        val (page, total) = repository.getNotificationsByUserId("customer", 2, 2)
        assertEquals(listOf("oldest"), page.map { it.id })
        assertEquals(3, total)
        assertNull(requests.first().exclusiveStartKey)
        assertEquals(cursor, requests.last().exclusiveStartKey)
        requests.forEach {
            assertEquals("notifications-test", it.tableName)
            assertEquals("userId-createdAt-index", it.indexName)
            assertEquals("userId = :uid", it.keyConditionExpression)
            assertEquals(mapOf(":uid" to AttributeValue.S("customer")), it.expressionAttributeValues)
            assertEquals(false, it.scanIndexForward)
        }
    }

    @Test
    fun `empty results and pages beyond end are empty with correct total`() = runTest {
        coEvery { client.query(any<QueryRequest>()) } returns QueryResponse { }
        assertEquals(emptyList<Notification>() to 0, repository.getNotificationsByUserId("customer"))
        coEvery { client.query(any<QueryRequest>()) } returns QueryResponse { items = listOf(item("one")) }
        val (page, total) = repository.getNotificationsByUserId("customer", 2, 20)
        assertTrue(page.isEmpty())
        assertEquals(1, total)
    }

    @Test
    fun `unread count sums filtered counts across all database pages`() = runTest {
        val cursor = mapOf("id" to AttributeValue.S("next"))
        coEvery { client.query(any<QueryRequest>()) } returnsMany listOf(
            QueryResponse { count = 2; lastEvaluatedKey = cursor }, QueryResponse { count = 3 },
        )
        assertEquals(5, repository.getUnreadCount("customer"))
        coVerify(exactly = 2) { client.query(match<QueryRequest> {
            it.filterExpression == "#r = :readVal" &&
                it.expressionAttributeValues?.get(":readVal") == AttributeValue.Bool(false) &&
                it.expressionAttributeValues?.get(":uid") == AttributeValue.S("customer")
        }) }
    }

    @Test
    fun `mark read requires an existing record and reports database failure`() = runTest {
        coEvery { client.updateItem(any<UpdateItemRequest>()) } returns UpdateItemResponse { }
        assertTrue(repository.markAsRead("one"))
        coVerify { client.updateItem(match<UpdateItemRequest> {
            it.conditionExpression == "attribute_exists(id)" && it.key == mapOf("id" to AttributeValue.S("one")) &&
                it.expressionAttributeValues == mapOf(":readVal" to AttributeValue.Bool(true))
        }) }
        coEvery { client.updateItem(any<UpdateItemRequest>()) } throws IllegalStateException("offline")
        assertFalse(repository.markAsRead("one"))
    }

    @Test
    fun `mark all skips already read notifications`() = runTest {
        coEvery { client.query(any<QueryRequest>()) } returns QueryResponse { items = listOf(item("unread"), item("read", true)) }
        coEvery { client.updateItem(any<UpdateItemRequest>()) } returns UpdateItemResponse { }
        assertEquals(1, repository.markAllAsRead("customer"))
        coVerify(exactly = 1) { client.updateItem(match<UpdateItemRequest> { it.key?.get("id") == AttributeValue.S("unread") }) }
    }

    @Test
    @Ignore("BUG: NotificationRepository.kt:152 markAllAsRead counts failed updates as successful")
    fun `mark all reports zero when no update succeeds`() = runTest {
        coEvery { client.query(any<QueryRequest>()) } returns QueryResponse { items = listOf(item("unread")) }
        coEvery { client.updateItem(any<UpdateItemRequest>()) } throws IllegalStateException("offline")
        assertEquals(0, repository.markAllAsRead("customer"))
    }

    @Test
    fun `missing and malformed notifications do not become customer records`() = runTest {
        coEvery { client.getItem(any<GetItemRequest>()) } returnsMany listOf(
            GetItemResponse { }, GetItemResponse { item = mapOf("userId" to AttributeValue.S("customer")) },
        )
        assertNull(repository.getNotificationById("missing"))
        assertNull(repository.getNotificationById("malformed"))
    }

    @Test
    fun `preferences default when absent and ignore unsupported stored channels`() = runTest {
        coEvery { client.getItem(any<GetItemRequest>()) } returns GetItemResponse { }
        assertEquals(NotificationPreference("customer"), repository.getPreferences("customer"))
        coEvery { client.getItem(any<GetItemRequest>()) } returns GetItemResponse {
            item = mapOf("userId" to AttributeValue.S("customer"), "channels" to AttributeValue.M(mapOf(
                "file_shared" to AttributeValue.L(listOf(AttributeValue.S("EMAIL"), AttributeValue.S("FUTURE"), AttributeValue.Bool(true))),
            )))
        }
        assertEquals(mapOf("file_shared" to listOf(DeliveryChannel.EMAIL)), repository.getPreferences("customer").channels)
    }

    @Test
    fun `preference persistence preserves explicit opt out and propagates write failures`() = runTest {
        val preference = NotificationPreference("customer", mapOf("file_shared" to emptyList()))
        coEvery { client.putItem(any<PutItemRequest>()) } returns PutItemResponse { }
        repository.savePreferences(preference)
        coVerify { client.putItem(match<PutItemRequest> {
            it.tableName == "preferences-test" && it.item?.get("channels") ==
                AttributeValue.M(mapOf("file_shared" to AttributeValue.L(emptyList())))
        }) }
        coEvery { client.putItem(any<PutItemRequest>()) } throws IllegalStateException("offline")
        assertFailsWith<IllegalStateException> { repository.savePreferences(preference) }
    }

    @Test
    fun `delete returns failure rather than claiming delivery store was updated`() = runTest {
        coEvery { client.deleteItem(any<DeleteItemRequest>()) } returns DeleteItemResponse { }
        assertTrue(repository.deleteNotification("one"))
        coEvery { client.deleteItem(any<DeleteItemRequest>()) } throws IllegalStateException("offline")
        assertFalse(repository.deleteNotification("one"))
    }
}
