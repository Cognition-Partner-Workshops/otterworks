package com.otterworks.notification.consumer

import aws.sdk.kotlin.services.sqs.SqsClient
import aws.sdk.kotlin.services.sqs.model.DeleteMessageRequest
import aws.sdk.kotlin.services.sqs.model.Message
import aws.sdk.kotlin.services.sqs.model.MessageAttributeValue
import aws.sdk.kotlin.services.sqs.model.ReceiveMessageRequest
import aws.sdk.kotlin.services.sqs.model.SendMessageRequest
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
    private val deadLetteredCounter: Counter? =
        meterRegistry?.counter("notifications.messages.deadlettered")

    // Producers and the SNS envelope carry fields this service does not declare,
    // so unknown keys are ignored. Field types stay strict; the timestamp field
    // accepts both RFC 3339 strings and epoch numbers via EventTimestampSerializer.
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = false
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
                    launch {
                        try {
                            handleMessage(msg)
                        } catch (e: Exception) {
                            logger.error(e) { "Error processing SQS message: ${msg.messageId}" }
                        }
                    }
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
     * Processes one received message.
     *
     * A message that cannot be parsed will never succeed, so it is moved to the
     * dead-letter queue (when configured) and deleted; leaving it in the queue
     * would make it reappear after every visibility timeout. A message that
     * parses but fails downstream is left in place so SQS redelivers it.
     */
    internal suspend fun handleMessage(msg: Message) {
        val body = msg.body
        val event = body?.let(::parseMessage)

        if (event == null) {
            processingErrorsCounter?.increment()
            logger.warn { "SQS message ${msg.messageId} cannot be parsed (${body?.length ?: 0} bytes); dead-lettering it" }
            deadLetter(msg, reason = if (body == null) "empty body" else "deserialization failed")
            return
        }

        notificationService.processEvent(event)
        delete(msg)
        logger.debug { "Deleted SQS message: ${msg.messageId}" }
    }

    internal fun parseMessage(body: String): SqsNotificationMessage? {
        return try {
            // Try parsing as direct message first
            json.decodeFromString<SqsNotificationMessage>(body)
        } catch (direct: Exception) {
            try {
                // Try unwrapping SNS envelope
                val snsWrapper = json.decodeFromString<SnsEnvelope>(body)
                json.decodeFromString<SqsNotificationMessage>(snsWrapper.Message)
            } catch (envelope: Exception) {
                logger.error(envelope) {
                    "Failed to parse message body as an event (${direct.message}) or as an SNS envelope"
                }
                null
            }
        }
    }

    private suspend fun deadLetter(msg: Message, reason: String) {
        val dlqUrl = config.sqsDeadLetterQueueUrl
        if (dlqUrl != null) {
            sqsClient.sendMessage(
                SendMessageRequest {
                    queueUrl = dlqUrl
                    messageBody = msg.body ?: ""
                    messageAttributes = mapOf(
                        "failureReason" to stringAttribute(reason),
                        "sourceMessageId" to stringAttribute(msg.messageId ?: "unknown"),
                        "sourceQueueUrl" to stringAttribute(config.sqsQueueUrl),
                    )
                },
            )
        } else {
            logger.warn { "SQS_DLQ_URL is not set; dropping unparseable SQS message ${msg.messageId}" }
        }
        delete(msg)
        deadLetteredCounter?.increment()
    }

    private suspend fun delete(msg: Message) {
        sqsClient.deleteMessage(
            DeleteMessageRequest {
                queueUrl = config.sqsQueueUrl
                receiptHandle = msg.receiptHandle
            },
        )
    }

    private fun stringAttribute(value: String) = MessageAttributeValue {
        dataType = "String"
        stringValue = value
    }
}

@kotlinx.serialization.Serializable
internal data class SnsEnvelope(
    val Message: String,
    val MessageId: String = "",
    val TopicArn: String = "",
    val Type: String = "",
)
