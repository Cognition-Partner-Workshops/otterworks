package com.otterworks.notification.health

import aws.sdk.kotlin.services.dynamodb.DynamoDbClient
import aws.sdk.kotlin.services.dynamodb.describeTable
import aws.sdk.kotlin.services.dynamodb.model.ResourceNotFoundException
import mu.KotlinLogging

private val logger = KotlinLogging.logger {}

class TableStartupCheck(
    private val dynamoDbClient: DynamoDbClient,
    val tableName: String,
) {
    @Volatile
    var isReady: Boolean = false
        private set

    suspend fun run(): Boolean {
        isReady = false
        return try {
            dynamoDbClient.describeTable { tableName = this@TableStartupCheck.tableName }
            isReady = true
            logger.info { "DynamoDB table $tableName is available" }
            true
        } catch (e: ResourceNotFoundException) {
            logger.error {
                "DynamoDB table $tableName not found; notification-service stays unready and the SQS consumer is not started"
            }
            false
        } catch (e: Exception) {
            logger.error {
                "DynamoDB table $tableName check failed: ${e.message}; notification-service stays unready and the SQS consumer is not started"
            }
            false
        }
    }
}
