package com.otterworks.notification.startup

import aws.sdk.kotlin.services.dynamodb.DynamoDbClient
import aws.sdk.kotlin.services.dynamodb.model.DescribeTableRequest
import aws.sdk.kotlin.services.dynamodb.model.ResourceNotFoundException
import com.otterworks.notification.config.AppConfig
import mu.KotlinLogging
import java.util.concurrent.atomic.AtomicBoolean

private val logger = KotlinLogging.logger {}

class TableStartupCheck(
    private val dynamoDbClient: DynamoDbClient,
    private val config: AppConfig,
) {
    private val ready = AtomicBoolean(false)

    val isReady: Boolean
        get() = ready.get()

    val tableName: String
        get() = config.dynamoDbTableNotifications

    suspend fun run(): Boolean {
        return try {
            dynamoDbClient.describeTable(
                DescribeTableRequest {
                    tableName = config.dynamoDbTableNotifications
                }
            )
            ready.set(true)
            logger.info { "DynamoDB table '${config.dynamoDbTableNotifications}' found; notification-service ready" }
            true
        } catch (e: ResourceNotFoundException) {
            logger.error { "DynamoDB table '${config.dynamoDbTableNotifications}' (DYNAMODB_TABLE_NOTIFICATIONS) not found; readiness failing and SQS consumer not started" }
            false
        } catch (e: Exception) {
            logger.error { "DynamoDB table '${config.dynamoDbTableNotifications}' check failed: ${e.message}" }
            false
        }
    }
}
