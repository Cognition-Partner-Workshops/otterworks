package com.otterworks.analytics.service

import akka.actor.testkit.typed.scaladsl.ActorTestKit
import akka.actor.typed.ActorSystem
import com.otterworks.analytics.config.AppConfig
import com.otterworks.analytics.model.{AnalyticsEvent, EventType}
import com.otterworks.analytics.repository.{InMemoryMetricsRepository, MetricsRepository}
import com.otterworks.analytics.config.PostgresConfig
import com.otterworks.analytics.service.EventProcessor.Outcome
import org.scalatest.BeforeAndAfterAll
import org.scalatest.concurrent.ScalaFutures
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import org.scalatest.time.{Millis, Seconds, Span}
import software.amazon.awssdk.services.sqs.SqsClient
import software.amazon.awssdk.services.sqs.model.{DeleteMessageRequest, DeleteMessageResponse, Message}

import java.time.Instant
import scala.collection.mutable
import scala.concurrent.{ExecutionContext, Future}

class EventProcessorSpec extends AnyFlatSpec with Matchers with ScalaFutures with BeforeAndAfterAll:

  given PatienceConfig = PatienceConfig(timeout = Span(5, Seconds), interval = Span(50, Millis))

  private val testKit = ActorTestKit()
  given ActorSystem[?] = testKit.system
  given ExecutionContext = testKit.system.executionContext

  override def afterAll(): Unit = testKit.shutdownTestKit()

  private val config = AppConfig.load()

  /** Records deletes; every other SqsClient call fails as unsupported. */
  private final class RecordingSqsClient(failDeletes: Boolean = false) extends SqsClient:
    val deleted: mutable.Buffer[String] = mutable.Buffer.empty
    override def serviceName(): String = "sqs"
    override def close(): Unit = ()
    override def deleteMessage(r: DeleteMessageRequest): DeleteMessageResponse =
      if failDeletes then throw new RuntimeException("delete failed")
      deleted.synchronized(deleted += r.receiptHandle())
      DeleteMessageResponse.builder().build()

  private def newRepo() = new InMemoryMetricsRepository(PostgresConfig("", "", "", 1))

  private def processor(repo: MetricsRepository, client: SqsClient) =
    new EventProcessor(config, new AnalyticsService(repo), _ => client)

  private def message(body: String, id: String = "sqs-msg-1", receipt: String = "rh-1") =
    Message.builder().messageId(id).receiptHandle(receipt).body(body).build()

  private def snsEnvelope(inner: String, snsId: String = "11111111-aaaa-bbbb-cccc-000000000001") =
    io.circe.Json.obj(
      "Type" -> io.circe.Json.fromString("Notification"),
      "MessageId" -> io.circe.Json.fromString(snsId),
      "TopicArn" -> io.circe.Json.fromString("arn:aws:sns:us-east-1:000000000000:otterworks-events-dev"),
      "Message" -> io.circe.Json.fromString(inner)
    ).noSpaces

  // services/file-service/src/events.rs FileEvent
  private val fileUploaded =
    """{"eventType":"file_uploaded","fileId":"f-1","ownerId":"u-1","folderId":null,"sharedWithUserId":null,"timestamp":"2026-10-06T18:00:00Z","name":"a.txt","mimeType":"text/plain","sizeBytes":42}"""
  // services/document-service/app/services/event_publisher.py envelope
  private val documentCreated =
    """{"event_type":"document_created","timestamp":"2026-10-06T18:00:01.500000+00:00","payload":{"id":"d-1","title":"Doc","content":"body","owner_id":"u-2","tags":[]}}"""
  private val native =
    """{"eventType":"document.viewed","userId":"u-3","resourceId":"d-9","resourceType":"document","metadata":{"title":"T"}}"""

  "EventProcessor.parseMessage" should "unwrap the SNS envelope and map a file-service event" in {
    val e = EventProcessor.parseMessage(snsEnvelope(fileUploaded), "sqs-1").toOption.get
    e.eventId shouldBe "sns-11111111-aaaa-bbbb-cccc-000000000001"
    e.eventType shouldBe EventType.FileUploaded
    e.userId shouldBe "u-1"
    e.resourceId shouldBe "f-1"
    e.resourceType shouldBe "file"
    e.metadata shouldBe Map("name" -> "a.txt", "mimeType" -> "text/plain", "sizeBytes" -> "42")
    e.timestamp shouldBe Instant.parse("2026-10-06T18:00:00Z")
  }

  it should "map a document-service event and drop document content from metadata" in {
    val e = EventProcessor.parseMessage(snsEnvelope(documentCreated), "sqs-1").toOption.get
    e.eventType shouldBe EventType.DocumentCreated
    e.userId shouldBe "u-2"
    e.resourceId shouldBe "d-1"
    e.resourceType shouldBe "document"
    e.metadata shouldBe Map("title" -> "Doc")
    e.timestamp shouldBe Instant.parse("2026-10-06T18:00:01.5Z")
  }

  it should "accept the native analytics payload with raw message delivery" in {
    val e = EventProcessor.parseMessage(native, "sqs-7").toOption.get
    e.eventId shouldBe "sqs-sqs-7"
    e.eventType shouldBe EventType.DocumentViewed
    e.metadata shouldBe Map("title" -> "T")
  }

  it should "derive the same event id when SNS redelivers the same notification" in {
    val a = EventProcessor.parseMessage(snsEnvelope(fileUploaded), "sqs-a").toOption.get
    val b = EventProcessor.parseMessage(snsEnvelope(fileUploaded), "sqs-b").toOption.get
    a.eventId shouldBe b.eventId
  }

  it should "reject malformed and unrecognised bodies" in {
    EventProcessor.parseMessage("not-json{", "m").isLeft shouldBe true
    EventProcessor.parseMessage(snsEnvelope("not-json{"), "m").isLeft shouldBe true
    EventProcessor.parseMessage("""{"hello":"world"}""", "m").isLeft shouldBe true
  }

  "EventProcessor.processMessage" should "store then delete a decodable SNS-wrapped event" in {
    val repo = newRepo()
    val client = RecordingSqsClient()
    processor(repo, client).processMessage(message(snsEnvelope(fileUploaded))).futureValue shouldBe Outcome.Stored
    repo.getEventCount.futureValue shouldBe 1L
    client.deleted.toList shouldBe List("rh-1")
  }

  it should "leave an undecodable message on the queue for redrive" in {
    val repo = newRepo()
    val client = RecordingSqsClient()
    processor(repo, client).processMessage(message("not-json{")).futureValue shouldBe Outcome.Rejected
    repo.getEventCount.futureValue shouldBe 0L
    client.deleted shouldBe empty
  }

  it should "not delete the message when storing the event fails" in {
    val failing = new MetricsRepository:
      private val delegate = newRepo()
      export delegate.{storeEvent as _, *}
      def storeEvent(event: AnalyticsEvent): Future[Unit] = Future.failed(new RuntimeException("db down"))
    val client = RecordingSqsClient()
    processor(failing, client).processMessage(message(snsEnvelope(fileUploaded))).futureValue shouldBe Outcome.Failed
    client.deleted shouldBe empty
  }

  it should "store a redelivered message only once after a failed delete" in {
    val repo = newRepo()
    val failingDelete = RecordingSqsClient(failDeletes = true)
    processor(repo, failingDelete)
      .processMessage(message(snsEnvelope(fileUploaded), id = "sqs-a", receipt = "rh-a"))
      .futureValue shouldBe Outcome.StoredNotDeleted

    val client = RecordingSqsClient()
    processor(repo, client)
      .processMessage(message(snsEnvelope(fileUploaded), id = "sqs-b", receipt = "rh-b"))
      .futureValue shouldBe Outcome.Stored

    repo.getEventCount.futureValue shouldBe 1L
    repo.getDashboardSummary("90d").futureValue.filesUploaded shouldBe 1L
    client.deleted.toList shouldBe List("rh-b")
  }
