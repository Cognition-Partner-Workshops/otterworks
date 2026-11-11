package com.otterworks.analytics.service

import io.circe.parser.parse
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class EventProcessorEnvelopeSpec extends AnyFlatSpec with Matchers:

  private val event =
    """{"eventType":"file_shared","userId":"user-1","resourceId":"file-123","resourceType":"file"}"""

  // Envelope shape captured from LocalStack EventBridge -> SQS (tests/eventbus/evidence/after-eventbridge).
  "unwrapEventBridge" should "return the detail of an EventBridge delivery" in {
    val body =
      s"""{"version":"0","id":"b38867ad","detail-type":"file_shared","source":"otterworks.file-service","account":"000000000000","time":"2026-11-11T18:44:12Z","region":"us-east-1","resources":[],"detail":$event}"""
    parse(EventProcessor.unwrapEventBridge(body)) shouldBe parse(event)
  }

  it should "leave a plain event unchanged" in {
    EventProcessor.unwrapEventBridge(event) shouldBe event
  }

  it should "leave an SNS envelope unchanged" in {
    val sns = """{"Type":"Notification","TopicArn":"arn:aws:sns:us-east-1:000000000000:otterworks-events","Message":"{}"}"""
    EventProcessor.unwrapEventBridge(sns) shouldBe sns
  }

  it should "leave non-JSON unchanged" in {
    EventProcessor.unwrapEventBridge("not json") shouldBe "not json"
  }
