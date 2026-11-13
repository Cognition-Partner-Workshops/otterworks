using System.Text;
using System.Text.Json;
using Payments.Models;
using Payments.Repositories;

namespace Payments.Services;

public sealed class WebhookService(
    PaymentRepository repository,
    WebhookSigner signer,
    IHttpClientFactory clients,
    TimeProvider clock)
{
    public async Task<WebhookEvent> Record(string dealerId, string eventType, int settlementId)
    {
        var body = JsonSerializer.Serialize(new { eventType, settlementId, dealerId });
        var entry = new WebhookEvent
        {
            DealerId = dealerId,
            Body = body,
            Signature = signer.Sign(body),
            CreatedAt = clock.GetUtcNow()
        };
        await repository.AddEvent(entry);
        return entry;
    }

    public async Task<bool> SendSample(string dealerId, string url)
    {
        var entry = await Record(dealerId, "settlement.sample", 0);
        using var message = new HttpRequestMessage(HttpMethod.Post, url);
        message.Content = new StringContent(entry.Body, Encoding.UTF8, "application/json");
        message.Headers.Add("X-Payments-Signature", entry.Signature);
        using var response = await clients.CreateClient("webhooks").SendAsync(message);
        return response.IsSuccessStatusCode;
    }
}
