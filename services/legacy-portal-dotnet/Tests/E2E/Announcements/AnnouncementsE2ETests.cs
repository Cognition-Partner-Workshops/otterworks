using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using OtterWorks.LegacyPortal.Announcements.Data;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.E2E.Announcements;

/// <summary>Announcements against a real PostgreSQL 15 (shared container; assertions scoped to rows each test creates).</summary>
public class AnnouncementsE2ETests : IClassFixture<PostgresPortalFactory>
{
    private readonly PostgresPortalFactory _factory;

    public AnnouncementsE2ETests(PostgresPortalFactory factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task Full_lifecycle_create_get_publish_list()
    {
        using var client = _factory.CreateClient();

        var draft = await CreateAsync(client, "lifecycle-draft", false);
        draft.GetProperty("published").GetBoolean().Should().BeFalse();
        var id = draft.GetProperty("id").GetInt64();
        var createdAt = draft.GetProperty("createdAt").GetString();

        using (var get = await client.GetAsync(Uri($"/api/announcements/{id}")))
        {
            get.StatusCode.Should().Be(HttpStatusCode.OK);
            (await get.Content.ReadAsStringAsync()).Should().Be(draft.GetRawText());
        }

        (await ListIdsAsync(client, "/api/announcements")).Should().NotContain(id);

        using (var publish = await client.PostAsync(Uri($"/api/announcements/{id}/publish"), null))
        {
            publish.StatusCode.Should().Be(HttpStatusCode.OK);
            using var json = JsonDocument.Parse(await publish.Content.ReadAsStringAsync());
            json.RootElement.GetProperty("published").GetBoolean().Should().BeTrue();
            json.RootElement.GetProperty("createdAt").GetString().Should().Be(createdAt);
        }

        (await ListIdsAsync(client, "/api/announcements")).Should().Contain(id);

        using var missing = await client.GetAsync(Uri("/api/announcements/987654321"));
        missing.StatusCode.Should().Be(HttpStatusCode.NotFound);
        (await missing.Content.ReadAsStringAsync()).Should()
            .Be("{\"error\":\"Not Found\",\"message\":\"announcement 987654321 not found\"}");
    }

    [Fact]
    public async Task Created_at_round_trips_with_microsecond_precision()
    {
        using var client = _factory.CreateClient();

        var created = await CreateAsync(client, "precision", true);
        var id = created.GetProperty("id").GetInt64();

        using var get = await client.GetAsync(Uri($"/api/announcements/{id}"));
        using var json = JsonDocument.Parse(await get.Content.ReadAsStringAsync());
        json.RootElement.GetProperty("createdAt").GetString().Should().Be(created.GetProperty("createdAt").GetString());
    }

    [Fact]
    public async Task Published_list_is_newest_first_and_all_list_is_physical_order()
    {
        using var client = _factory.CreateClient();

        var a = (await CreateAsync(client, "order-a", true)).GetProperty("id").GetInt64();
        var b = (await CreateAsync(client, "order-b", false)).GetProperty("id").GetInt64();
        var c = (await CreateAsync(client, "order-c", true)).GetProperty("id").GetInt64();

        (await ListIdsAsync(client, "/api/announcements")).Where(new[] { a, c }.Contains).Should().Equal(c, a);

        using (var publish = await client.PostAsync(Uri($"/api/announcements/{b}/publish"), null))
        {
            publish.StatusCode.Should().Be(HttpStatusCode.OK);
        }

        var mine = new[] { a, b, c };
        (await ListIdsAsync(client, "/api/announcements?publishedOnly=false")).Where(mine.Contains).Should().Equal(a, c, b);
        (await ListIdsAsync(client, "/api/announcements?publishedOnly=true")).Where(mine.Contains).Should().Equal(c, b, a);
    }

    [Fact]
    public async Task Validation_errors_return_spring_bodies_and_persist_nothing()
    {
        using var client = _factory.CreateClient();
        var before = await CountAsync();

        foreach (var body in new[] { "{\"title\":\"\",\"body\":\"b\"}", "{\"title\":\"t\"}", "{bad", string.Empty })
        {
            using var response = await PostJsonAsync(client, body);
            response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
            using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            json.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal("timestamp", "status", "error", "path");
        }

        using var tooLong = await PostJsonAsync(client, JsonSerializer.Serialize(new { title = new string('t', 201), body = "b" }));
        tooLong.StatusCode.Should().Be(HttpStatusCode.BadRequest);

        using var bad = await client.GetAsync(Uri("/api/announcements?publishedOnly=perhaps"));
        bad.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        (await bad.Content.ReadAsStringAsync()).Should()
            .Be("{\"error\":\"Bad Request\",\"message\":\"Invalid boolean value [perhaps]\"}");

        (await CountAsync()).Should().Be(before);
    }

    [Fact]
    public async Task Max_length_values_fit_the_varchar_columns()
    {
        using var client = _factory.CreateClient();

        using var response = await PostJsonAsync(
            client, JsonSerializer.Serialize(new { title = new string('t', 200), body = new string('b', 4000), published = true }));

        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    [Fact]
    public async Task Concurrent_creates_get_distinct_ids_and_concurrent_publishes_succeed()
    {
        using var client = _factory.CreateClient();

        var created = await Task.WhenAll(Enumerable.Range(0, 20).Select(i => CreateAsync(client, $"concurrent-{i}", false)));
        var ids = created.Select(e => e.GetProperty("id").GetInt64()).ToList();
        ids.Should().OnlyHaveUniqueItems();

        var published = await Task.WhenAll(ids.Select(async id =>
        {
            using var response = await client.PostAsync(Uri($"/api/announcements/{id}/publish"), null);
            response.StatusCode.Should().Be(HttpStatusCode.OK);
            using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            return json.RootElement.GetProperty("published").GetBoolean();
        }));

        published.Should().AllSatisfy(p => p.Should().BeTrue());
        (await ListIdsAsync(client, "/api/announcements")).Should().Contain(ids);
    }

    [Fact]
    public async Task Schema_matches_hibernate_ddl_and_initializer_is_idempotent()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AnnouncementsDbContext>();
        await new AnnouncementsSchemaInitializer(db).InitializeAsync(CancellationToken.None);

        var columns = await db.Database.SqlQueryRaw<string>(
            "SELECT column_name || ' ' || data_type || coalesce('(' || character_maximum_length || ')', '') || ' ' || is_nullable " +
            "|| coalesce(' ' || column_default, '') AS \"Value\" FROM information_schema.columns " +
            "WHERE table_schema = 'announcements' AND table_name = 'announcement' ORDER BY ordinal_position").ToListAsync();

        columns.Should().Equal(
            "id bigint NO nextval('announcements.announcement_id_seq'::regclass)",
            "body character varying(4000) NO",
            "created_at timestamp without time zone NO",
            "published boolean NO",
            "title character varying(200) NO");
    }

    private static Uri Uri(string path) => new(path, UriKind.Relative);

    private static async Task<HttpResponseMessage> PostJsonAsync(HttpClient client, string body)
    {
        using var content = new StringContent(body, Encoding.UTF8);
        content.Headers.ContentType = new MediaTypeHeaderValue("application/json");
        return await client.PostAsync(Uri("/api/announcements"), content);
    }

    private static async Task<JsonElement> CreateAsync(HttpClient client, string title, bool published)
    {
        using var response = await PostJsonAsync(client, JsonSerializer.Serialize(new { title, body = title + " body", published }));
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        await Task.Delay(2);
        return json.RootElement.Clone();
    }

    private static async Task<List<long>> ListIdsAsync(HttpClient client, string path)
    {
        using var response = await client.GetAsync(Uri(path));
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        return json.RootElement.EnumerateArray().Select(e => e.GetProperty("id").GetInt64()).ToList();
    }

    private async Task<int> CountAsync()
    {
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AnnouncementsDbContext>();
        return await db.Announcements.CountAsync();
    }
}
