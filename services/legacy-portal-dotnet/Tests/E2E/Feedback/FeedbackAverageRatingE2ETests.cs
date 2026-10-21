using System.Net;
using System.Text;
using System.Text.Json;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.E2E.Feedback;

/// <summary>Runs against its own fresh PostgreSQL container so the table starts empty.</summary>
public class FeedbackAverageRatingE2ETests : IClassFixture<PostgresPortalFactory>
{
    private readonly PostgresPortalFactory _factory;

    public FeedbackAverageRatingE2ETests(PostgresPortalFactory factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task Average_rating_matches_java_from_empty_table_to_non_integral()
    {
        using var client = _factory.CreateClient();

        (await client.GetStringAsync("/api/feedback/average-rating")).Should().Be("{\"averageRating\":0.0}");

        await SubmitAsync(client, "u1", 5, "great");
        await SubmitAsync(client, "u1", 3, "ok");
        await SubmitAsync(client, "u2", 1, "bad");
        (await client.GetStringAsync("/api/feedback/average-rating")).Should().Be("{\"averageRating\":3.0}");

        using var rejected = await PostAsync(client, "{\"userId\":\"u1\",\"rating\":9,\"message\":\"bad rating\"}");
        rejected.StatusCode.Should().Be(HttpStatusCode.BadRequest);

        await SubmitAsync(client, "u3", 4, "string rating");
        await SubmitAsync(client, "u3", 2, "meh");
        await SubmitAsync(client, "u3", 4, "float rating");
        (await client.GetStringAsync("/api/feedback/average-rating?extra=1")).Should().Be("{\"averageRating\":3.1666666666666665}");
    }

    private static async Task<HttpResponseMessage> PostAsync(HttpClient client, string json)
    {
        using var content = new StringContent(json, Encoding.UTF8, "application/json");
        return await client.PostAsync("/api/feedback", content);
    }

    private static async Task SubmitAsync(HttpClient client, string userId, int rating, string message)
    {
        using var response = await PostAsync(client, JsonSerializer.Serialize(new { userId, rating, message }));
        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }
}
