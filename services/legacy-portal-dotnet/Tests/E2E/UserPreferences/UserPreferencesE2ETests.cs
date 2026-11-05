using System.Net;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using OtterWorks.LegacyPortal.Tests.Support;
using OtterWorks.LegacyPortal.Tests.Unit.UserPreferences;
using OtterWorks.LegacyPortal.UserPreferences.Data;

namespace OtterWorks.LegacyPortal.Tests.E2E.UserPreferences;

public sealed class UserPreferencesE2ETests : IClassFixture<PostgresPortalFactory>, IDisposable
{
    private readonly WebApplicationFactory<Program> _factory;
    private readonly HttpClient _client;

    public UserPreferencesE2ETests(PostgresPortalFactory fixture)
    {
        _factory = fixture.WithUserPreferencesStore();
        _client = _factory.CreateClient();
    }

    public void Dispose()
    {
        _client.Dispose();
        _factory.Dispose();
    }

    [Fact]
    public async Task Schema_initializer_creates_the_hibernate_table_shape()
    {
        var columns = await QueryAsync(
            "SELECT column_name || ':' || data_type || ':' || COALESCE(character_maximum_length::text, '-') || ':' || is_nullable "
            + "FROM information_schema.columns WHERE table_schema = 'user_preferences' AND table_name = 'user_preference' ORDER BY ordinal_position");
        var primaryKey = await QueryAsync(
            "SELECT kcu.column_name FROM information_schema.table_constraints tc "
            + "JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
            + "WHERE tc.table_schema = 'user_preferences' AND tc.table_name = 'user_preference' AND tc.constraint_type = 'PRIMARY KEY'");

        columns.Should().Equal(
            "user_id:character varying:100:NO",
            "email_notifications:boolean:-:NO",
            "locale:character varying:20:NO",
            "theme:character varying:20:NO");
        primaryKey.Should().Equal("user_id");
    }

    [Fact]
    public async Task Schema_initializer_is_idempotent()
    {
        using var scope = _factory.Services.CreateScope();
        var initializer = new UserPreferencesSchemaInitializer(scope.ServiceProvider.GetRequiredService<UserPreferencesDbContext>());

        await initializer.InitializeAsync(CancellationToken.None);
        await initializer.InitializeAsync(CancellationToken.None);
    }

    [Fact]
    public async Task Full_lifecycle_defaults_insert_update_read()
    {
        var userId = NewUser();

        (await Body(await Send(HttpMethod.Get, userId))).Should().Be(Expected(userId, "light", "en-US", true));
        (await RowCount(userId)).Should().Be(0);

        (await Body(await Send(HttpMethod.Put, userId, "{\"theme\": \"dark\", \"locale\": \"fr-FR\", \"emailNotifications\": false}")))
            .Should().Be(Expected(userId, "dark", "fr-FR", false));
        (await Body(await Send(HttpMethod.Get, userId))).Should().Be(Expected(userId, "dark", "fr-FR", false));
        (await RowCount(userId)).Should().Be(1);

        (await Body(await Send(HttpMethod.Put, userId, "{\"theme\": \"light\", \"locale\": \"en-US\"}")))
            .Should().Be(Expected(userId, "light", "en-US", false));
        (await Body(await Send(HttpMethod.Put, userId, "{\"theme\":\"dark\",\"locale\":\"de-DE\",\"emailNotifications\":\"true\"}")))
            .Should().Be(Expected(userId, "dark", "de-DE", true));
        (await Body(await Send(HttpMethod.Get, userId))).Should().Be(Expected(userId, "dark", "de-DE", true));
        (await RowCount(userId)).Should().Be(1);
        (await QueryAsync($"SELECT theme || '|' || locale || '|' || email_notifications::text FROM user_preferences.user_preference WHERE user_id = '{userId}'"))
            .Should().Equal("dark|de-DE|true");
    }

    [Fact]
    public async Task Sequential_writes_are_last_writer_wins()
    {
        var userId = NewUser();
        foreach (var theme in new[] { "a", "b", "c", "d" })
        {
            (await Send(HttpMethod.Put, userId, $"{{\"theme\":\"{theme}\",\"locale\":\"en-US\",\"emailNotifications\":true}}")).Dispose();
        }

        (await Body(await Send(HttpMethod.Get, userId))).Should().Be(Expected(userId, "d", "en-US", true));
    }

    [Theory]
    [InlineData("{\"locale\": \"en-GB\", \"emailNotifications\": true}")]
    [InlineData("{\"theme\": \"ttttttttttttttttttttt\", \"locale\": \"en-GB\"}")]
    [InlineData("{\"theme\": \"dark\", \"locale\": \"  \"}")]
    [InlineData("{not json")]
    public async Task Validation_errors_return_spring_400_and_do_not_write(string body)
    {
        var userId = NewUser();

        using var response = await Send(HttpMethod.Put, userId, body);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        json.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal("timestamp", "status", "error", "path");
        json.RootElement.GetProperty("path").GetString().Should().Be($"/api/preferences/{userId}");
        (await RowCount(userId)).Should().Be(0);
    }

    [Fact]
    public async Task Text_plain_returns_415_and_unsupported_methods_return_405()
    {
        using var unsupported = await Send(HttpMethod.Put, "u2", "theme=dark", "text/plain");
        using var post = await Send(HttpMethod.Post, "u1", "{\"theme\": \"dark\", \"locale\": \"en-US\"}");
        using var delete = await Send(HttpMethod.Delete, "u1");
        using var noId = await _client.GetAsync(new Uri("/api/preferences/", UriKind.Relative));

        unsupported.StatusCode.Should().Be(HttpStatusCode.UnsupportedMediaType);
        post.StatusCode.Should().Be(HttpStatusCode.MethodNotAllowed);
        delete.StatusCode.Should().Be(HttpStatusCode.MethodNotAllowed);
        noId.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task Url_encoded_user_id_round_trips_through_the_database()
    {
        var userId = $"user with space {Guid.NewGuid():N}";
        var path = Uri.EscapeDataString(userId);

        (await Body(await Send(HttpMethod.Put, path, "{\"theme\":\"dark\",\"locale\":\"en-US\",\"emailNotifications\":true}")))
            .Should().Be(Expected(userId, "dark", "en-US", true));
        (await RowCount(userId)).Should().Be(1);
    }

    [Fact]
    public async Task User_id_longer_than_column_returns_spring_500_like_hibernate()
    {
        var userId = new string('x', 101);

        using var response = await Send(HttpMethod.Put, userId, "{\"theme\":\"dark\",\"locale\":\"en-US\",\"emailNotifications\":true}");

        response.StatusCode.Should().Be(HttpStatusCode.InternalServerError);
        using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        json.RootElement.GetProperty("error").GetString().Should().Be("Internal Server Error");
    }

    [Fact]
    public async Task Concurrent_upserts_for_distinct_users_all_persist()
    {
        var users = Enumerable.Range(0, 20).Select(_ => NewUser()).ToList();

        var responses = await Task.WhenAll(users.Select(u => Send(HttpMethod.Put, u, "{\"theme\":\"dark\",\"locale\":\"nl-NL\",\"emailNotifications\":true}")));

        foreach (var response in responses)
        {
            response.StatusCode.Should().Be(HttpStatusCode.OK);
            response.Dispose();
        }

        foreach (var user in users)
        {
            (await Body(await Send(HttpMethod.Get, user))).Should().Be(Expected(user, "dark", "nl-NL", true));
        }
    }

    [Fact]
    public async Task Concurrent_updates_to_an_existing_user_succeed_and_leave_one_of_the_written_values()
    {
        var userId = NewUser();
        (await Send(HttpMethod.Put, userId, "{\"theme\":\"seed\",\"locale\":\"en-US\",\"emailNotifications\":true}")).Dispose();
        var themes = Enumerable.Range(0, 10).Select(i => $"theme-{i}").ToList();

        var responses = await Task.WhenAll(themes.Select(t => Send(HttpMethod.Put, userId, $"{{\"theme\":\"{t}\",\"locale\":\"en-US\",\"emailNotifications\":false}}")));

        foreach (var response in responses)
        {
            response.StatusCode.Should().Be(HttpStatusCode.OK);
            response.Dispose();
        }

        using var final = JsonDocument.Parse(await Body(await Send(HttpMethod.Get, userId)));
        themes.Should().Contain(final.RootElement.GetProperty("theme").GetString());
        (await RowCount(userId)).Should().Be(1);
    }

    private static string NewUser() => $"e2e-{Guid.NewGuid():N}";

    private static string Expected(string userId, string theme, string locale, bool emailNotifications) =>
        JsonSerializer.Serialize(new { userId, theme, locale, emailNotifications });

    private static async Task<string> Body(HttpResponseMessage response)
    {
        using (response)
        {
            response.StatusCode.Should().Be(HttpStatusCode.OK);
            return await response.Content.ReadAsStringAsync();
        }
    }

    private async Task<HttpResponseMessage> Send(HttpMethod method, string userId, string? body = null, string contentType = "application/json")
    {
        using var request = new HttpRequestMessage(method, new Uri($"/api/preferences/{userId}", UriKind.Relative));
        request.Headers.Accept.ParseAdd("application/json");
        if (body is not null)
        {
            request.Content = new StringContent(body, Encoding.UTF8, contentType);
        }

        return await _client.SendAsync(request);
    }

    private async Task<int> RowCount(string userId)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<UserPreferencesDbContext>();
        return await context.Preferences.AsNoTracking().CountAsync(p => p.UserId == userId);
    }

    private async Task<List<string>> QueryAsync(string sql)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<UserPreferencesDbContext>();
        return await context.Database.SqlQueryRaw<string>(sql).ToListAsync();
    }
}
