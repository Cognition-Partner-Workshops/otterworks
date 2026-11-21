using System.Text.Json;

namespace OtterWorks.AuditService.Services;

/// <summary>Strips the SNS or EventBridge delivery envelope from an SQS message body.</summary>
public static class MessageEnvelope
{
    public static string Unwrap(string body)
    {
        try
        {
            using var doc = JsonDocument.Parse(body);
            var root = doc.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                return body;
            }

            if (root.TryGetProperty("detail-type", out _)
                && root.TryGetProperty("detail", out var detail)
                && detail.ValueKind == JsonValueKind.Object)
            {
                return detail.GetRawText();
            }

            if (root.TryGetProperty("Message", out var messageElement))
            {
                return messageElement.GetString() ?? body;
            }
        }
        catch (JsonException)
        {
            // Not JSON; the caller's deserializer reports it.
        }

        return body;
    }
}
