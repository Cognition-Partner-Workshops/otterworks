package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import aws.sdk.kotlin.services.sqs.model.DeleteMessageRequest
import aws.sdk.kotlin.services.sqs.model.Message
import aws.sdk.kotlin.services.sqs.model.ReceiveMessageRequest
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.model.SqsNotificationMessage
import com.otterworks.notification.service.NotificationService
import io.micrometer.core.instrument.Counter
import io.micrometer.core.instrument.MeterRegistry
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import mu.KotlinLogging

private val logger = KotlinLogging.logger {}

class SqsConsumer(
    private val sqsClient: SqsClient,
    private val notificationService: NotificationService,
    private val config: AppConfig,
    meterRegistry: MeterRegistry? = null,
) {
    private val processingErrorsCounter: Counter? =
        meterRegistry?.counter("notifications.processing.errors")
    private val malformedMessagesCounter: Counter? =
        meterRegistry?.counter("notifications.messages.malformed")

    // The queue carries events from several publishers and service versions, so the
    // parser must tolerate fields it does not know about. Timestamp shape differences
    // (RFC 3339 string vs. epoch number) are absorbed by EventTimestampSerializer.
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    suspend fun startPolling() = coroutineScope {
        logger.info { "Starting SQS consumer polling: ${config.sqsQueueUrl}" }

        while (isActive) {
            try {
                val request = ReceiveMessageRequest {
                    queueUrl = config.sqsQueueUrl
                    maxNumberOfMessages = config.sqsMaxMessages
                    waitTimeSeconds = config.sqsWaitTimeSeconds
                }

                val response = sqsClient.receiveMessage(request)
                val messages = response.messages ?: emptyList()

                if (messages.isNotEmpty()) {
                    logger.info { "Received ${messages.size} messages from SQS" }
                }

                for (msg in messages) {
                    launch { handleMessage(msg) }
                }

                if (messages.isEmpty()) {
                    delay(config.sqsPollIntervalMs)
                }
            } catch (e: Exception) {
                logger.error(e) { "Error polling SQS" }
                delay(config.sqsPollIntervalMs * 2)
            }
        }
    }

    /**
     * Processes one message. A message whose body cannot be parsed can never succeed,
     * so it is counted, logged and removed from the queue rather than left to reappear
     * after every visibility timeout. Failures while handling a well-formed event are
     * transient (downstream dependencies) and leave the message in place so SQS
     * redelivers it and, past the redrive policy's maxReceiveCount, dead-letters it.
     */
    internal suspend fun handleMessage(msg: Message) {
        val body = msg.body
        if (body == null) {
            logger.warn { "SQS message ${msg.messageId} has no body; deleting" }
            deleteMessage(msg)
            return
        }

        val event = parseMessage(body)
        if (event == null) {
            processingErrorsCounter?.increment()
            malformedMessagesCounter?.increment()
            logger.error { "Malformed SQS message ${msg.messageId}; removing from queue. body=$body" }
            deleteMessage(msg)
            return
        }

        try {
            notificationService.processEvent(event)
        } catch (e: Exception) {
            processingErrorsCounter?.increment()
            logger.error(e) { "Error processing SQS message ${msg.messageId}; leaving for redelivery" }
            return
        }

        deleteMessage(msg)
        logger.debug { "Deleted SQS message: ${msg.messageId}" }
    }

    private suspend fun deleteMessage(msg: Message) {
        try {
            sqsClient.deleteMessage(
                DeleteMessageRequest {
                    queueUrl = config.sqsQueueUrl
                    receiptHandle = msg.receiptHandle
                },
            )
        } catch (e: Exception) {
            logger.error(e) { "Failed to delete SQS message ${msg.messageId}" }
        }
    }

    internal fun parseMessage(body: String): SqsNotificationMessage? {
        return try {
            // Try parsing as direct message first
            json.decodeFromString<SqsNotificationMessage>(body)
        } catch (_: Exception) {
            try {
                // Try unwrapping SNS envelope
                val snsWrapper = json.decodeFromString<SnsEnvelope>(body)
                json.decodeFromString<SqsNotificationMessage>(snsWrapper.Message)
            } catch (e: Exception) {
                logger.error(e) { "Failed to parse message body" }
                null
            }
        }
    }
}

@kotlinx.serialization.Serializable
internal data class SnsEnvelope(
    val Message: String,
    val MessageId: String = "",
    val TopicArn: String = "",
    val Type: String = "",
)
