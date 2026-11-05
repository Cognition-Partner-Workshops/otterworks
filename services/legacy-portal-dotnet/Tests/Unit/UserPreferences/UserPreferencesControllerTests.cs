using System.Net;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.Unit.UserPreferences;

public sealed class UserPreferencesControllerTests : IClassFixture<InMemoryPortalFactory>, IDisposable
{
    private readonly WebApplicationFactory<Program> _factory;
    private readonly HttpClient _client;

    public UserPreferencesControllerTests(InMemoryPortalFactory factory)
    {
        _factory = factory.WithUserPreferencesStore();
        _client = _factory.CreateClient();
    }

    public void Dispose()
    {
        _client.Dispose();
        _factory.Dispose();
    }

    [Fact]
    public async Task Get_unknown_user_returns_defaults_and_does_not_persist()
    {
        var userId = NewUser();

        await AssertPreference(await Send(HttpMethod.Get, userId), userId, "light", "en-US", true);

        await Send(HttpMethod.Put, userId, "{\"theme\":\"dark\",\"locale\":\"fr-FR\"}");
        await Send(HttpMethod.Get, NewUser());
        await AssertPreference(await Send(HttpMethod.Get, userId), userId, "dark", "fr-FR", false);
    }

    [Fact]
    public async Task Put_upserts_and_returns_body_in_java_property_order()
    {
        var userId = NewUser();

        using var created = await Send(HttpMethod.Put, userId, "{\"theme\": \"dark\", \"locale\": \"fr-FR\", \"emailNotifications\": false}");
        (await created.Content.ReadAsStringAsync())
            .Should().Be($"{{\"userId\":\"{userId}\",\"theme\":\"dark\",\"locale\":\"fr-FR\",\"emailNotifications\":false}}");
        created.Content.Headers.ContentType!.MediaType.Should().Be("application/json");

        await AssertPreference(await Send(HttpMethod.Put, userId, "{\"theme\":\"light\",\"locale\":\"en-US\",\"emailNotifications\":true}"), userId, "light", "en-US", true);
        await AssertPreference(await Send(HttpMethod.Get, userId), userId, "light", "en-US", true);
    }

    [Theory]
    [InlineData("{\"theme\": \"light\", \"locale\": \"en-US\"}", false)]
    [InlineData("{\"theme\":\"dark\",\"locale\":\"de-DE\",\"emailNotifications\":\"true\"}", true)]
    [InlineData("{\"theme\":\"dark\",\"locale\":\"de-DE\",\"emailNotifications\":null}", false)]
    [InlineData("{\"theme\":\"dark\",\"locale\":\"de-DE\",\"emailNotifications\":true,\"unknown\":1}", true)]
    public async Task Put_coerces_email_notifications_like_jackson(string body, bool expected)
    {
        var userId = NewUser();
        using var response = await Send(HttpMethod.Put, userId, body);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        json.RootElement.GetProperty("emailNotifications").GetBoolean().Should().Be(expected);
    }

    [Fact]
    public async Task Put_coerces_scalar_theme_to_string()
    {
        var userId = NewUser();

        await AssertPreference(await Send(HttpMethod.Put, userId, "{\"theme\":123,\"locale\":\"en-US\",\"emailNotifications\":true}"), userId, "123", "en-US", true);
    }

    [Theory]
    [InlineData("{\"locale\": \"en-GB\", \"emailNotifications\": true}")]
    [InlineData("{\"theme\": \"ttttttttttttttttttttt\", \"locale\": \"en-GB\"}")]
    [InlineData("{\"theme\": \"dark\", \"locale\": \"  \"}")]
    [InlineData("{\"theme\": \"dark\", \"locale\": \"\"}")]
    [InlineData("{\"theme\": \"dark\", \"locale\": \"lllllllllllllllllllll\"}")]
    [InlineData("{\"theme\": null, \"locale\": \"en-US\"}")]
    [InlineData("{not json")]
    [InlineData("")]
    [InlineData("null")]
    [InlineData("[]")]
    [InlineData("{\"theme\":{},\"locale\":\"en-US\"}")]
    [InlineData("{\"theme\":\"dark\",\"locale\":\"en-US\",\"emailNotifications\":\"maybe\"}")]
    public async Task Put_with_invalid_body_returns_spring_400(string body)
    {
        var userId = NewUser();

        using var response = await Send(HttpMethod.Put, userId, body);

        await AssertSpringError(response, 400, "Bad Request", $"/api/preferences/{userId}");
        await AssertPreference(await Send(HttpMethod.Get, userId), userId, "light", "en-US", true);
    }

    [Fact]
    public async Task Put_with_text_plain_returns_415()
    {
        using var response = await Send(HttpMethod.Put, "u2", "theme=dark", "text/plain");

        await AssertSpringError(response, 415, "Unsupported Media Type", "/api/preferences/u2");
    }

    [Theory]
    [InlineData("POST")]
    [InlineData("DELETE")]
    [InlineData("PATCH")]
    public async Task Unsupported_methods_return_405(string method)
    {
        using var response = await Send(new HttpMethod(method), "u1", method == "DELETE" ? null : "{\"theme\": \"dark\", \"locale\": \"en-US\"}");

        await AssertSpringError(response, 405, "Method Not Allowed", "/api/preferences/u1");
    }

    [Fact]
    public async Task Get_without_user_id_returns_spring_404()
    {
        using var response = await _client.GetAsync(new Uri("/api/preferences/", UriKind.Relative));

        await AssertSpringError(response, 404, "Not Found", "/api/preferences/");
    }

    [Fact]
    public async Task User_id_is_url_decoded()
    {
        using var response = await _client.GetAsync(new Uri("/api/preferences/user%20with%20space", UriKind.Relative));

        await AssertPreference(response, "user with space", "light", "en-US", true);
    }

    private static string NewUser() => $"user-{Guid.NewGuid():N}";

    private static async Task AssertPreference(HttpResponseMessage response, string userId, string theme, string locale, bool emailNotifications)
    {
        using (response)
        {
            response.StatusCode.Should().Be(HttpStatusCode.OK);
            var body = await response.Content.ReadAsStringAsync();
            body.Should().Be(JsonSerializer.Serialize(new { userId, theme, locale, emailNotifications }));
        }
    }

    private static async Task AssertSpringError(HttpResponseMessage response, int status, string error, string path)
    {
        ((int)response.StatusCode).Should().Be(status);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        json.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal("timestamp", "status", "error", "path");
        json.RootElement.GetProperty("timestamp").GetString().Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$");
        json.RootElement.GetProperty("status").GetInt32().Should().Be(status);
        json.RootElement.GetProperty("error").GetString().Should().Be(error);
        json.RootElement.GetProperty("path").GetString().Should().Be(path);
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
}
