using System.Net;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using OtterWorks.LegacyPortal.Feedback.Data;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.E2E.Feedback;

public class FeedbackLifecycleE2ETests : IClassFixture<PostgresPortalFactory>
{
    private static readonly string[] SpringErrorKeys = ["timestamp", "status", "error", "path"];

    private readonly PostgresPortalFactory _factory;

    public FeedbackLifecycleE2ETests(PostgresPortalFactory factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task Submit_then_list_round_trips_through_postgres_newest_first()
    {
        using var client = _factory.CreateClient();
        var user = NewUser();

        var first = await SubmitAsync(client, user, 5, "great");
        await Task.Delay(5);
        var second = await SubmitAsync(client, user, 3, "ok");
        await SubmitAsync(client, NewUser(), 1, "someone else");

        var listJson = await client.GetStringAsync($"/api/feedback?userId={user}");

        using var list = JsonDocument.Parse(listJson);
        list.RootElement.GetArrayLength().Should().Be(2);
        list.RootElement[0].GetRawText().Should().Be(second.RootElement.GetRawText());
        list.RootElement[1].GetRawText().Should().Be(first.RootElement.GetRawText());
        second.RootElement.GetProperty("id").GetInt64().Should().BeGreaterThan(first.RootElement.GetProperty("id").GetInt64());
        first.RootElement.GetProperty("createdAt").GetString().Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.(\d{3}|\d{6}))?Z$");
    }

    [Fact]
    public async Task Coerced_ratings_are_persisted_as_integers()
    {
        using var client = _factory.CreateClient();
        var user = NewUser();

        using var stringRating = await PostJsonAsync(client, $"{{\"userId\":\"{user}\",\"rating\":\"4\",\"message\":\"string rating\"}}");
        using var floatRating = await PostJsonAsync(client, $"{{\"userId\":\"{user}\",\"rating\":4.7,\"message\":\"float rating\"}}");

        stringRating.StatusCode.Should().Be(HttpStatusCode.Created);
        floatRating.StatusCode.Should().Be(HttpStatusCode.Created);
        using var list = JsonDocument.Parse(await client.GetStringAsync($"/api/feedback?userId={user}"));
        list.RootElement.EnumerateArray().Select(e => e.GetProperty("rating").GetInt32()).Should().Equal(4, 4);
    }

    [Theory]
    [InlineData("{\"userId\":\"u1\",\"rating\":9,\"message\":\"bad rating\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":null,\"message\":\"rating null\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":4,\"message\":\"\"}")]
    [InlineData("{\"userId\":")]
    public async Task Invalid_submissions_return_spring_400_and_are_not_persisted(string json)
    {
        using var client = _factory.CreateClient();
        var before = await CountRowsAsync();

        using var response = await PostJsonAsync(client, json);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        body.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal(SpringErrorKeys);
        body.RootElement.GetProperty("path").GetString().Should().Be("/api/feedback");
        (await CountRowsAsync()).Should().Be(before);
    }

    [Fact]
    public async Task Missing_user_id_is_400_and_empty_user_id_is_empty_list()
    {
        using var client = _factory.CreateClient();

        using var missing = await client.GetAsync("/api/feedback");
        using var empty = await client.GetAsync("/api/feedback?userId=");

        missing.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        empty.StatusCode.Should().Be(HttpStatusCode.OK);
        (await empty.Content.ReadAsStringAsync()).Should().Be("[]");
    }

    [Fact]
    public async Task Unsupported_media_type_and_method_return_spring_errors()
    {
        using var client = _factory.CreateClient();
        using var content = new StringContent("rating=5", Encoding.UTF8, "text/plain");

        using var plain = await client.PostAsync("/api/feedback", content);
        using var delete = await client.DeleteAsync("/api/feedback");

        plain.StatusCode.Should().Be(HttpStatusCode.UnsupportedMediaType);
        delete.StatusCode.Should().Be(HttpStatusCode.MethodNotAllowed);
    }

    [Fact]
    public async Task Concurrent_submissions_get_unique_ids_and_are_all_listed()
    {
        using var client = _factory.CreateClient();
        var user = NewUser();
        const int count = 25;

        var responses = await Task.WhenAll(Enumerable.Range(0, count).Select(async i =>
        {
            using var response = await PostJsonAsync(client, JsonSerializer.Serialize(new { userId = user, rating = (i % 5) + 1, message = $"m{i}" }));
            response.StatusCode.Should().Be(HttpStatusCode.Created);
            using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            return body.RootElement.GetProperty("id").GetInt64();
        }));

        responses.Should().OnlyHaveUniqueItems();
        using var list = JsonDocument.Parse(await client.GetStringAsync($"/api/feedback?userId={user}"));
        list.RootElement.EnumerateArray().Select(e => e.GetProperty("id").GetInt64()).Should().BeEquivalentTo(responses);
        var createdAt = list.RootElement.EnumerateArray()
            .Select(e => DateTime.Parse(e.GetProperty("createdAt").GetString()!, System.Globalization.CultureInfo.InvariantCulture, System.Globalization.DateTimeStyles.AdjustToUniversal))
            .ToList();
        createdAt.Should().BeInDescendingOrder();
    }

    [Fact]
    public async Task Schema_matches_hibernate_ddl()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<FeedbackDbContext>();
        var connection = db.Database.GetDbConnection();
        await connection.OpenAsync();
        try
        {
            await using var command = connection.CreateCommand();
            command.CommandText =
                "SELECT column_name, data_type, COALESCE(character_maximum_length, 0), is_nullable, COALESCE(column_default, '') " +
                "FROM information_schema.columns WHERE table_schema = 'feedback' AND table_name = 'feedback' ORDER BY ordinal_position";
            var columns = new List<string>();
            await using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                {
                    columns.Add($"{reader.GetString(0)}|{reader.GetString(1)}|{reader.GetInt32(2)}|{reader.GetString(3)}|{reader.GetString(4)}");
                }
            }

            columns.Should().Equal(
                "id|bigint|0|NO|nextval('feedback.feedback_id_seq'::regclass)",
                "created_at|timestamp without time zone|0|NO|",
                "message|character varying|2000|NO|",
                "rating|integer|0|NO|",
                "user_id|character varying|100|NO|");
        }
        finally
        {
            await connection.CloseAsync();
        }
    }

    private static string NewUser() => $"e2e-{Guid.NewGuid():N}";

    private static async Task<HttpResponseMessage> PostJsonAsync(HttpClient client, string json)
    {
        using var content = new StringContent(json, Encoding.UTF8, "application/json");
        return await client.PostAsync("/api/feedback", content);
    }

    private static async Task<JsonDocument> SubmitAsync(HttpClient client, string userId, int rating, string message)
    {
        using var response = await PostJsonAsync(client, JsonSerializer.Serialize(new { userId, rating, message }));
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        return JsonDocument.Parse(await response.Content.ReadAsStringAsync());
    }

    private async Task<int> CountRowsAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<FeedbackDbContext>();
        return await db.Entries.CountAsync();
    }
}
