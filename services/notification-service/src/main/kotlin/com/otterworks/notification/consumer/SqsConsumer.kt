package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import aws.sdk.kotlin.services.sqs.model.DeleteMessageRequest
import aws.sdk.kotlin.services.sqs.model.Message
import aws.sdk.kotlin.services.sqs.model.QueueAttributeName
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

private const val RECEIVE_COUNT_ATTRIBUTE = "ApproximateReceiveCount"

class SqsConsumer(
    private val sqsClient: SqsClient,
    private val notificationService: NotificationService,
    private val config: AppConfig,
    meterRegistry: MeterRegistry? = null,
) {
    private val processingErrorsCounter: Counter? =
        meterRegistry?.counter("notifications.processing.errors")
    private val poisonMessagesCounter: Counter? =
        meterRegistry?.counter("notifications.processing.poison")

    // Producers of several generations publish to this queue, so the consumer
    // must accept every shape they emit: unknown keys are ignored and the
    // timestamp field is normalised by EventTimestampSerializer (RFC 3339
    // string or epoch integer). Never tighten this to a strict schema.
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
                    attributeNames = listOf(QueueAttributeName.fromValue(RECEIVE_COUNT_ATTRIBUTE))
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

    internal suspend fun handleMessage(msg: Message) {
        val body = msg.body ?: return
        val event = parseMessage(body)

        if (event == null) {
            processingErrorsCounter?.increment()
            val receiveCount = msg.attributes?.get(RECEIVE_COUNT_ATTRIBUTE)?.toIntOrNull() ?: 1
            if (receiveCount >= config.sqsMaxReceiveCount) {
                // A body that still does not parse after this many deliveries never
                // will; dropping it keeps the queue from refilling forever. A redrive
                // policy with a lower maxReceiveCount moves it to the DLQ first.
                poisonMessagesCounter?.increment()
                logger.error {
                    "Dropping unparseable SQS message ${msg.messageId} after $receiveCount receives: $body"
                }
                deleteMessage(msg)
            } else {
                logger.warn {
                    "Failed to parse SQS message ${msg.messageId} (receive $receiveCount of ${config.sqsMaxReceiveCount})"
                }
            }
            return
        }

        try {
            notificationService.processEvent(event)
            deleteMessage(msg)
        } catch (e: Exception) {
            processingErrorsCounter?.increment()
            logger.error(e) { "Error processing SQS message: ${msg.messageId}" }
        }
    }

    private suspend fun deleteMessage(msg: Message) {
        val deleteRequest = DeleteMessageRequest {
            queueUrl = config.sqsQueueUrl
            receiptHandle = msg.receiptHandle
        }
        sqsClient.deleteMessage(deleteRequest)
        logger.debug { "Deleted SQS message: ${msg.messageId}" }
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
