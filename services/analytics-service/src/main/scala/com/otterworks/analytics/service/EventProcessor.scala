package com.otterworks.analytics.service

import akka.actor.typed.ActorSystem
import akka.stream.RestartSettings
import akka.stream.scaladsl.{RestartSource, Sink, Source}
import com.otterworks.analytics.config.AppConfig
import com.otterworks.analytics.model.{AnalyticsEvent, EventType}
import io.circe.JsonObject
import io.circe.parser.parse
import io.prometheus.client.Counter
import org.slf4j.LoggerFactory
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration
import software.amazon.awssdk.core.retry.RetryMode
import software.amazon.awssdk.regions.Region
import software.amazon.awssdk.services.sqs.SqsClient
import software.amazon.awssdk.services.sqs.model.{DeleteMessageRequest, Message, ReceiveMessageRequest}

import java.net.URI
import java.time.{Instant, OffsetDateTime}
import scala.concurrent.{blocking, ExecutionContext, Future}
import scala.concurrent.duration.*
import scala.jdk.CollectionConverters.*
import scala.util.{Failure, Success, Try}

/**
 * SQS-based event processor that consumes analytics events from a queue
 * and feeds them into the AnalyticsService for processing and storage.
 *
 * Uses Akka Streams for backpressure-aware processing of incoming events.
 */
class EventProcessor(
    config: AppConfig,
    analyticsService: AnalyticsService,
    sqsClientFactory: AppConfig => SqsClient = EventProcessor.defaultSqsClient
)(using system: ActorSystem[?], ec: ExecutionContext):

  import EventProcessor.*

  private val logger = LoggerFactory.getLogger(getClass)

  private lazy val sqsClient: SqsClient = sqsClientFactory(config)

  /**
   * Start polling SQS for events. This runs as an Akka Stream that
   * periodically receives messages, processes them, and deletes them
   * from the queue only after they have been durably stored. The stream is
   * restarted with jittered backoff if it ever fails.
   */
  def start(): Unit =
    logger.info("Starting SQS event processor, queue={}", config.sqs.eventsQueueUrl)

    RestartSource
      .onFailuresWithBackoff(RestartSettings(1.second, 30.seconds, 0.2)) { () =>
        Source
          .tick(1.second, 5.seconds, ())
          .mapAsync(1)(_ => receiveBatch())
          .mapConcat(identity)
          .mapAsync(4)(message => Future.delegate(processMessage(message)))
      }
      .runWith(Sink.ignore)
      .onComplete {
        case Success(_)  => logger.warn("SQS event processor stream completed")
        case Failure(ex) => logger.error("SQS event processor stream terminated", ex)
      }

    logger.info("SQS event processor stream started"): Unit

  private def receiveBatch(): Future[List[Message]] =
    Future {
      blocking {
        Try {
          val request = ReceiveMessageRequest.builder()
            .queueUrl(config.sqs.eventsQueueUrl)
            .maxNumberOfMessages(10)
            .waitTimeSeconds(2)
            .attributeNamesWithStrings("ApproximateReceiveCount")
            .build()
          sqsClient.receiveMessage(request).messages().asScala.toList
        } match
          case Success(msgs) => msgs
          case Failure(ex) =>
            logger.warn("Failed to receive messages from SQS, will retry", ex)
            List.empty
      }
    }

  /**
   * Process one SQS message. The message is deleted only after the event has
   * been stored; anything that cannot be decoded or stored is left on the
   * queue so it is redelivered after the visibility timeout and, once
   * maxReceiveCount is exceeded, moved to the queue's dead-letter queue.
   */
  private[service] def processMessage(message: Message): Future[Outcome] =
    parseMessage(message.body(), message.messageId()) match
      case Left(err) =>
        logger.error(
          "Leaving undecodable SQS message {} on the queue (receiveCount={}): {}",
          message.messageId(),
          receiveCount(message),
          err
        )
        messagesTotal.labels(Outcome.Rejected.label).inc()
        Future.successful(Outcome.Rejected)
      case Right(event) =>
        analyticsService
          .ingestEvent(event)
          .map { stored =>
            Try {
              val deleteReq = DeleteMessageRequest.builder()
                .queueUrl(config.sqs.eventsQueueUrl)
                .receiptHandle(message.receiptHandle())
                .build()
              sqsClient.deleteMessage(deleteReq)
            } match
              case Success(_) =>
                logger.debug("Processed SQS event: {}", stored.eventId)
                Outcome.Stored
              case Failure(ex) =>
                logger.error("Failed to delete SQS message for event {}: {}", stored.eventId, ex.getMessage)
                Outcome.StoredNotDeleted
          }
          .recover { case ex =>
            logger.error(
              "Failed to store event from SQS message {}; leaving it for redelivery: {}",
              message.messageId(),
              ex.getMessage
            )
            Outcome.Failed
          }
          .map { outcome =>
            messagesTotal.labels(outcome.label).inc()
            outcome
          }

  private def receiveCount(message: Message): String =
    Option(message.attributesAsStrings().get("ApproximateReceiveCount")).getOrElse("?")

object EventProcessor:

  enum Outcome(val label: String):
    case Stored extends Outcome("stored")
    case StoredNotDeleted extends Outcome("stored_not_deleted")
    case Rejected extends Outcome("rejected")
    case Failed extends Outcome("failed")

  val messagesTotal: Counter = Counter.build()
    .name("analytics_sqs_messages_total")
    .help("SQS messages handled by the analytics event processor, by outcome")
    .labelNames("outcome")
    .register()

  /**
   * Bounded SDK deadlines: each attempt (including the 2s long poll) must
   * finish within 10s and the whole call, retries included, within 30s.
   * STANDARD retry mode caps attempts at 3 with jittered exponential backoff.
   */
  def defaultSqsClient(config: AppConfig): SqsClient =
    val builder = SqsClient.builder()
      .region(Region.of(config.aws.region))
      .credentialsProvider(DefaultCredentialsProvider.create())
      .overrideConfiguration(
        ClientOverrideConfiguration.builder()
          .apiCallAttemptTimeout(java.time.Duration.ofSeconds(10))
          .apiCallTimeout(java.time.Duration.ofSeconds(30))
          .retryPolicy(RetryMode.STANDARD)
          .build()
      )
    config.aws.endpointUrl.foreach(url => builder.endpointOverride(URI.create(url)))
    builder.build()

  private val producerEventTypes: Map[String, String] = Map(
    "document_created" -> EventType.DocumentCreated,
    "document_created_from_template" -> EventType.DocumentCreated,
    "document_updated" -> EventType.DocumentEdited,
    "document_patched" -> EventType.DocumentEdited,
    "document_deleted" -> EventType.DocumentDeleted,
    "document_shared" -> EventType.DocumentShared,
    "file_uploaded" -> EventType.FileUploaded,
    "file_downloaded" -> EventType.FileDownloaded,
    "file_deleted" -> EventType.FileDeleted,
    "file_shared" -> EventType.FileShared
  )

  private def normalizeEventType(raw: String): String =
    if raw.contains('.') then raw
    else producerEventTypes.getOrElse(raw, raw.replaceFirst("_", "."))

  private def parseInstant(s: String): Option[Instant] =
    Try(OffsetDateTime.parse(s).toInstant).orElse(Try(Instant.parse(s))).toOption

  private def scalarFields(obj: JsonObject, exclude: Set[String]): Map[String, String] =
    obj.toList.collect {
      case (k, v) if !exclude.contains(k) && v.isString => k -> v.asString.get
      case (k, v) if !exclude.contains(k) && (v.isNumber || v.isBoolean) => k -> v.noSpaces
    }.toMap

  private def str(obj: JsonObject, key: String): Option[String] =
    obj(key).flatMap(_.asString).filter(_.nonEmpty)

  /**
   * Decode an SQS message body into an analytics event.
   *
   * Accepts the SNS notification envelope (the analytics queue is an SNS
   * subscriber without raw message delivery) as well as a raw body, and the
   * three producer shapes on the topic: the native analytics payload, the
   * file-service camelCase event and the document-service `{event_type,
   * payload}` envelope. The event id is derived from the SNS (or SQS) message
   * id so a redelivered message maps to the same event and is stored once.
   */
  def parseMessage(body: String, sqsMessageId: String): Either[String, AnalyticsEvent] =
    for
      outer <- parse(body).left.map(e => s"invalid JSON: ${e.getMessage}")
      outerObj <- outer.asObject.toRight("message body is not a JSON object")
      (eventObj, eventId) <- unwrapSns(outerObj, sqsMessageId)
      event <- toEvent(eventObj, eventId)
    yield event

  private def unwrapSns(obj: JsonObject, sqsMessageId: String): Either[String, (JsonObject, String)] =
    (str(obj, "Type"), obj("Message").flatMap(_.asString)) match
      case (Some("Notification"), Some(inner)) =>
        val id = str(obj, "MessageId").map(id => s"sns-$id").getOrElse(s"sqs-$sqsMessageId")
        for
          json <- parse(inner).left.map(e => s"invalid JSON in SNS Message: ${e.getMessage}")
          innerObj <- json.asObject.toRight("SNS Message is not a JSON object")
        yield (innerObj, id)
      case _ => Right((obj, s"sqs-$sqsMessageId"))

  private def toEvent(obj: JsonObject, eventId: String): Either[String, AnalyticsEvent] =
    val timestamp = str(obj, "timestamp").flatMap(parseInstant).getOrElse(Instant.now())
    def event(eventType: String, userId: String, resourceId: String, resourceType: String, metadata: Map[String, String]) =
      AnalyticsEvent(eventId, normalizeEventType(eventType), userId, resourceId, resourceType, metadata, timestamp)

    val native =
      for
        eventType <- str(obj, "eventType")
        userId <- str(obj, "userId")
        resourceId <- str(obj, "resourceId")
        resourceType <- str(obj, "resourceType")
      yield
        val metadata = obj("metadata").flatMap(_.as[Map[String, String]].toOption).getOrElse(Map.empty)
        event(eventType, userId, resourceId, resourceType, metadata)

    val fileService =
      for
        eventType <- str(obj, "eventType")
        fileId <- str(obj, "fileId")
        ownerId <- str(obj, "ownerId")
      yield event(eventType, ownerId, fileId, "file", scalarFields(obj, Set("eventType", "fileId", "ownerId", "timestamp")))

    val documentService =
      for
        eventType <- str(obj, "event_type")
        payload <- obj("payload").flatMap(_.asObject)
        resourceId <- str(payload, "id").orElse(str(payload, "document_id"))
      yield
        val userId = str(payload, "owner_id").orElse(str(payload, "user_id")).getOrElse("unknown")
        val resourceType = str(payload, "type").getOrElse("document")
        event(eventType, userId, resourceId, resourceType, scalarFields(payload, Set("id", "owner_id", "user_id", "content", "type")))

    native
      .orElse(fileService)
      .orElse(documentService)
      .toRight(s"unrecognised event shape (fields: ${obj.keys.mkString(",")})")
