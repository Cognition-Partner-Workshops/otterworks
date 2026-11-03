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

internal const val RECEIVE_COUNT_ATTRIBUTE = "ApproximateReceiveCount"
private const val MAX_LOGGED_BODY_CHARS = 512

class SqsConsumer(
    private val sqsClient: SqsClient,
    private val notificationService: NotificationService,
    private val config: AppConfig,
    meterRegistry: MeterRegistry? = null,
) {
    private val processingErrorsCounter: Counter? =
        meterRegistry?.counter("notifications.processing.errors")
    private val discardedCounter: Counter? =
        meterRegistry?.counter("notifications.processing.discarded")

    // Producers add fields before this consumer learns about them, so unknown
    // keys are ignored. The timestamp wire format (RFC 3339 string or epoch
    // number) is normalised by FlexibleTimestampSerializer on the model, so the
    // parser settings never decide whether a legacy event is accepted.
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
            handleUnparseable(msg)
            return
        }

        try {
            notificationService.processEvent(event)
            deleteMessage(msg)
            logger.debug { "Deleted SQS message: ${msg.messageId}" }
        } catch (e: Exception) {
            processingErrorsCounter?.increment()
            logger.error(e) { "Error processing SQS message ${msg.messageId}; leaving it for redelivery" }
        }
    }

    // An unparseable message never succeeds on retry. Up to the queue's redrive
    // limit it is left alone so the dead-letter queue receives it; if it is still
    // being delivered past that limit the queue has no redrive policy, and the
    // message is dropped rather than cycling through the visibility timeout forever.
    private suspend fun handleUnparseable(msg: Message) {
        val receiveCount = msg.attributes?.get(RECEIVE_COUNT_ATTRIBUTE)?.toIntOrNull() ?: 1
        if (receiveCount <= config.sqsMaxReceiveCount) {
            logger.warn {
                "Failed to parse SQS message ${msg.messageId} (receive $receiveCount/${config.sqsMaxReceiveCount}); " +
                    "leaving it for the queue's redrive policy"
            }
            return
        }

        logger.error {
            "Discarding unparseable SQS message ${msg.messageId} after $receiveCount receives: " +
                msg.body?.take(MAX_LOGGED_BODY_CHARS)
        }
        discardedCounter?.increment()
        deleteMessage(msg)
    }

    private suspend fun deleteMessage(msg: Message) {
        val deleteRequest = DeleteMessageRequest {
            queueUrl = config.sqsQueueUrl
            receiptHandle = msg.receiptHandle
        }
        sqsClient.deleteMessage(deleteRequest)
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
