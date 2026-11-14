package com.otterworks.notification.service

import com.otterworks.notification.model.DeliveryChannel
import com.otterworks.notification.model.Notification
import com.otterworks.notification.model.NotificationPreference
import com.otterworks.notification.model.SqsNotificationMessage
import com.otterworks.notification.repository.NotificationRepository
import com.otterworks.notification.template.NotificationTemplates
import com.otterworks.notification.websocket.WebSocketManager
import io.micrometer.core.instrument.Counter
import io.micrometer.core.instrument.MeterRegistry
import mu.KotlinLogging
import java.time.Instant
import java.util.UUID

private val logger = KotlinLogging.logger {}

class NotificationService(
    private val repository: NotificationRepository,
    private val emailSender: EmailSender,
    private val webSocketManager: WebSocketManager,
    private val meterRegistry: MeterRegistry?,
) {
    private val processedCounter: Counter? = meterRegistry?.counter("notifications.processed")
    private val emailSentCounter: Counter? = meterRegistry?.counter("notifications.email.sent")
    private val pushSentCounter: Counter? = meterRegistry?.counter("notifications.push.sent")
    private val duplicateCounter: Counter? = meterRegistry?.counter("notifications.duplicates.skipped")

    /**
     * When [idempotencyKey] is set (the SNS/SQS message id), the notification id is derived from it
     * so a redelivered message maps to the same DynamoDB item and its side effects are skipped.
     */
    suspend fun processEvent(event: SqsNotificationMessage, idempotencyKey: String? = null) {
        val targetUserId = resolveTargetUserId(event)
        if (targetUserId.isBlank()) {
            logger.warn { "No target user for event: ${event.eventType}" }
            return
        }

        val notificationId = idempotencyKey?.let { notificationIdFor(it, targetUserId) }
            ?: UUID.randomUUID().toString()
        if (idempotencyKey != null && repository.getNotificationById(notificationId) != null) {
            duplicateCounter?.increment()
            logger.info { "Skipping duplicate delivery of $idempotencyKey (notification $notificationId)" }
            return
        }

        val preferences = repository.getPreferences(targetUserId)
        val enabledChannels = preferences.channels[event.eventType]
            ?: NotificationPreference(userId = targetUserId).channels[event.eventType]
            ?: listOf(DeliveryChannel.IN_APP)

        val rendered = NotificationTemplates.render(event)
        val deliveredVia = mutableListOf<String>()

        if (DeliveryChannel.IN_APP in enabledChannels) {
            deliveredVia.add("in_app")
        }

        // Attempt email delivery
        if (DeliveryChannel.EMAIL in enabledChannels) {
            val emailSent = emailSender.sendEmail(
                toAddress = "$targetUserId@otterworks.io",
                subject = rendered.emailSubject,
                htmlBody = rendered.emailBody,
            )
            if (emailSent) {
                deliveredVia.add("email")
                emailSentCounter?.increment()
            }
        }

        // Create notification and persist for audit trail and offline retrieval
        val notification = Notification(
            id = notificationId,
            userId = targetUserId,
            type = event.eventType,
            title = rendered.title,
            message = rendered.message,
            resourceId = resolveResourceId(event),
            resourceType = resolveResourceType(event),
            actorId = event.actorId.ifEmpty { event.ownerId },
            read = false,
            deliveredVia = deliveredVia,
            createdAt = Instant.now().toString(),
        )

        if (idempotencyKey == null) {
            repository.saveNotification(notification)
        } else if (!repository.createNotificationIfAbsent(notification)) {
            duplicateCounter?.increment()
            logger.info { "Skipping duplicate delivery of $idempotencyKey (notification $notificationId)" }
            return
        }
        logger.info { "Stored notification ${notification.id} for user $targetUserId" }

        // Attempt WebSocket push after save, then update record with actual delivery status
        if (DeliveryChannel.PUSH in enabledChannels) {
            val pushCount = webSocketManager.pushNotification(targetUserId, notification)
            if (pushCount > 0) {
                deliveredVia.add("push")
                pushSentCounter?.increment()
                repository.saveNotification(notification.copy(deliveredVia = deliveredVia))
                logger.info { "Pushed notification ${notification.id} to $pushCount session(s) for user $targetUserId" }
            }
        }

        processedCounter?.increment()
        logger.info {
            "Processed ${event.eventType} for user $targetUserId via ${deliveredVia.joinToString()}"
        }
    }

    suspend fun getNotifications(userId: String, page: Int, pageSize: Int) =
        repository.getNotificationsByUserId(userId, page, pageSize)

    suspend fun getUnreadCount(userId: String): Int =
        repository.getUnreadCount(userId)

    suspend fun markAsRead(notificationId: String): Boolean =
        repository.markAsRead(notificationId)

    suspend fun markAllAsRead(userId: String): Int =
        repository.markAllAsRead(userId)

    suspend fun deleteNotification(notificationId: String): Boolean =
        repository.deleteNotification(notificationId)

    suspend fun getNotificationById(id: String): Notification? =
        repository.getNotificationById(id)

    suspend fun getPreferences(userId: String): NotificationPreference =
        repository.getPreferences(userId)

    suspend fun updatePreferences(userId: String, eventType: String, channels: List<DeliveryChannel>) {
        val current = repository.getPreferences(userId)
        val updatedChannels = current.channels.toMutableMap()
        updatedChannels[eventType] = channels
        repository.savePreferences(current.copy(channels = updatedChannels))
    }

    companion object {
        fun notificationIdFor(idempotencyKey: String, targetUserId: String): String =
            UUID.nameUUIDFromBytes("$idempotencyKey|$targetUserId".toByteArray(Charsets.UTF_8)).toString()

        fun resolveTargetUserId(event: SqsNotificationMessage): String {
            return when (event.eventType) {
                "file_shared" -> event.sharedWithUserId
                "comment_added" -> event.userId.ifEmpty { event.ownerId }
                "document_edited" -> event.userId.ifEmpty { event.ownerId }
                "user_mentioned" -> event.mentionedUserId.ifEmpty { event.userId }
                else -> event.userId
            }
        }

        fun resolveResourceId(event: SqsNotificationMessage): String {
            return when (event.eventType) {
                "file_shared" -> event.fileId
                "comment_added" -> event.commentId.ifEmpty { event.documentId }
                "document_edited" -> event.documentId
                "user_mentioned" -> event.documentId
                else -> ""
            }
        }

        fun resolveResourceType(event: SqsNotificationMessage): String {
            return when (event.eventType) {
                "file_shared" -> "file"
                "comment_added" -> "comment"
                "document_edited" -> "document"
                "user_mentioned" -> "document"
                else -> "unknown"
            }
        }
    }
}
