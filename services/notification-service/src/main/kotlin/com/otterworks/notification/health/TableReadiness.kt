package com.otterworks.notification.health

import aws.sdk.kotlin.services.dynamodb.DynamoDbClient
import aws.sdk.kotlin.services.dynamodb.describeTable
import mu.KotlinLogging

class TableReadiness(private val dynamoDb: DynamoDbClient, private val tableName: String) {
    @Volatile
    var isReady: Boolean = false
        private set

    suspend fun check(): Boolean {
        return try {
            dynamoDb.describeTable { tableName = this@TableReadiness.tableName }
            isReady = true
            logger.info { "DynamoDB table '$tableName' is available" }
            isReady
        } catch (e: Exception) {
            isReady = false
            logger.error {
                "DynamoDB table '$tableName' is unavailable (${e::class.simpleName}: ${e.message}); " +
                    "notification-service stays unready and the SQS consumer is not started"
            }
            isReady
        }
    }

    private companion object {
        val logger = KotlinLogging.logger {}
    }
}
