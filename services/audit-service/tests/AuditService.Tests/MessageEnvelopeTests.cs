using System.Text.Json;
using OtterWorks.AuditService.Services;

namespace AuditService.Tests;

public class MessageEnvelopeTests
{
    private const string FileShared =
        "{\"eventType\":\"file_shared\",\"fileId\":\"file-123\",\"folderId\":null,\"ownerId\":\"owner-1\",\"sharedWithUserId\":\"user-2\",\"timestamp\":\"2026-11-11T18:00:00+00:00\"}";

    [Fact]
    public void Unwrap_SnsEnvelope_ReturnsMessage()
    {
        var body = JsonSerializer.Serialize(new
        {
            Type = "Notification",
            MessageId = "m-1",
            TopicArn = "arn:aws:sns:us-east-1:000000000000:otterworks-events",
            Message = FileShared,
        });

        Assert.Equal(FileShared, MessageEnvelope.Unwrap(body));
    }

    // Body shape captured from LocalStack EventBridge -> SQS (tests/eventbus/evidence/after-eventbridge).
    [Fact]
    public void Unwrap_EventBridgeEnvelope_ReturnsDetail()
    {
        var body = "{\"version\":\"0\",\"id\":\"b38867ad\",\"detail-type\":\"file_shared\",\"source\":\"otterworks.file-service\","
                   + "\"account\":\"000000000000\",\"time\":\"2026-11-11T18:44:12Z\",\"region\":\"us-east-1\",\"resources\":[],"
                   + "\"detail\":" + FileShared + "}";

        Assert.Equal(FileShared, MessageEnvelope.Unwrap(body));
    }

    [Fact]
    public void Unwrap_PlainEvent_ReturnsBodyUnchanged()
    {
        Assert.Equal(FileShared, MessageEnvelope.Unwrap(FileShared));
    }

    [Fact]
    public void Unwrap_NotJson_ReturnsBodyUnchanged()
    {
        Assert.Equal("not json", MessageEnvelope.Unwrap("not json"));
    }
}
