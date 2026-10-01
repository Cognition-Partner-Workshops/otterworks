using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.DependencyInjection;
using OtterWorks.LegacyPortal.Announcements.Data;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.Unit.Announcements;

/// <summary>Controller behaviour through the full HTTP pipeline on EF InMemory (fresh store per test).</summary>
public sealed class AnnouncementsControllerTests : IDisposable
{
    private readonly InMemoryPortalFactory _factory = new();
    private readonly HttpClient _client;

    public AnnouncementsControllerTests()
    {
        _client = _factory.CreateClient();
    }

    public void Dispose()
    {
        _client.Dispose();
        _factory.Dispose();
    }

    [Fact]
    public async Task Create_returns_201_with_java_property_order()
    {
        using var response = await PostJsonAsync("/api/announcements", "{\"title\":\"Release\",\"body\":\"v1 is out\",\"published\":true}");

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        using var json = await ReadJsonAsync(response);
        json.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal("id", "title", "body", "published", "createdAt");
        json.RootElement.GetProperty("id").GetInt64().Should().Be(1);
        json.RootElement.GetProperty("title").GetString().Should().Be("Release");
        json.RootElement.GetProperty("body").GetString().Should().Be("v1 is out");
        json.RootElement.GetProperty("published").GetBoolean().Should().BeTrue();
        json.RootElement.GetProperty("createdAt").GetString().Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$");
    }

    [Theory]
    [InlineData("{\"title\":\"t\",\"body\":\"b\"}", false)]
    [InlineData("{\"title\":\"t\",\"body\":\"b\",\"published\":null}", false)]
    [InlineData("{\"title\":\"t\",\"body\":\"b\",\"published\":\"true\"}", true)]
    [InlineData("{\"title\":\"t\",\"body\":\"b\",\"published\":1}", true)]
    [InlineData("{\"title\":\"t\",\"body\":\"b\",\"published\":false,\"extra\":{\"x\":[1]}}", false)]
    public async Task Create_coerces_published_and_ignores_unknown_properties(string body, bool expected)
    {
        using var response = await PostJsonAsync("/api/announcements", body);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        using var json = await ReadJsonAsync(response);
        json.RootElement.GetProperty("published").GetBoolean().Should().Be(expected);
    }

    [Fact]
    public async Task Create_coerces_numeric_title_to_string()
    {
        using var response = await PostJsonAsync("/api/announcements", "{\"title\":5,\"body\":\"b\"}");

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        using var json = await ReadJsonAsync(response);
        json.RootElement.GetProperty("title").GetString().Should().Be("5");
    }

    [Theory]
    [InlineData("{\"body\":\"b\"}")]
    [InlineData("{\"title\":\"   \",\"body\":\"b\"}")]
    [InlineData("{\"title\":\"t\",\"body\":\"\"}")]
    [InlineData("{\"Title\":\"t\",\"body\":\"b\"}")]
    [InlineData("{\"title\":\"t\",\"body\":\"b\",\"published\":\"yes\"}")]
    [InlineData("{\"title\":{},\"body\":\"b\"}")]
    [InlineData("{\"title\":\"t\",")]
    [InlineData("null")]
    [InlineData("[]")]
    [InlineData("")]
    public async Task Create_invalid_body_returns_spring_default_400(string body)
    {
        using var response = await PostJsonAsync("/api/announcements", body);

        await ShouldBeSpringErrorAsync(response, HttpStatusCode.BadRequest, "Bad Request", "/api/announcements");
    }

    [Theory]
    [InlineData(201, 1)]
    [InlineData(1, 4001)]
    public async Task Create_over_max_length_returns_400(int titleLength, int bodyLength)
    {
        var payload = JsonSerializer.Serialize(new { title = new string('t', titleLength), body = new string('b', bodyLength) });

        using var response = await PostJsonAsync("/api/announcements", payload);

        await ShouldBeSpringErrorAsync(response, HttpStatusCode.BadRequest, "Bad Request", "/api/announcements");
    }

    [Fact]
    public async Task Create_at_max_length_returns_201()
    {
        var payload = JsonSerializer.Serialize(new { title = new string('t', 200), body = new string('b', 4000) });

        using var response = await PostJsonAsync("/api/announcements", payload);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    [Theory]
    [InlineData("text/plain", "{\"title\":\"t\",\"body\":\"b\"}")]
    [InlineData("text/plain", "")]
    [InlineData("application/x-www-form-urlencoded", "title=t&body=b")]
    public async Task Create_unsupported_media_type_returns_415(string mediaType, string body)
    {
        using var content = new StringContent(body, Encoding.UTF8, mediaType);

        using var response = await _client.PostAsync(Uri("/api/announcements"), content);

        await ShouldBeSpringErrorAsync(response, HttpStatusCode.UnsupportedMediaType, "Unsupported Media Type", "/api/announcements");
    }

    [Fact]
    public async Task Create_without_content_type_and_body_returns_400()
    {
        using var content = new ByteArrayContent([]);

        using var response = await _client.PostAsync(Uri("/api/announcements"), content);

        await ShouldBeSpringErrorAsync(response, HttpStatusCode.BadRequest, "Bad Request", "/api/announcements");
    }

    [Fact]
    public async Task Create_without_content_type_but_with_body_returns_415()
    {
        using var content = new ByteArrayContent(Encoding.UTF8.GetBytes("{\"title\":\"t\",\"body\":\"b\"}"));

        using var response = await _client.PostAsync(Uri("/api/announcements"), content);

        response.StatusCode.Should().Be(HttpStatusCode.UnsupportedMediaType);
    }

    [Fact]
    public async Task List_defaults_to_published_only_newest_first()
    {
        await CreateAsync("draft", false);
        await CreateAsync("first", true);
        await CreateAsync("second", true);

        (await ListTitlesAsync("/api/announcements")).Should().Equal("second", "first");
        (await ListTitlesAsync("/api/announcements/")).Should().Equal("second", "first");
    }

    [Theory]
    [InlineData("?publishedOnly=false")]
    [InlineData("?publishedOnly=OFF")]
    [InlineData("?publishedOnly=%20no%20")]
    [InlineData("?publishedOnly=0")]
    public async Task List_published_only_false_returns_all_rows(string query)
    {
        await CreateAsync("draft", false);
        await CreateAsync("live", true);

        (await ListTitlesAsync("/api/announcements" + query)).Should().BeEquivalentTo("draft", "live");
    }

    [Theory]
    [InlineData("?publishedOnly=")]
    [InlineData("?publishedOnly=Yes")]
    [InlineData("?publishedOnly=1")]
    [InlineData("?publishedOnly=on")]
    public async Task List_published_only_truthy_or_empty_returns_published(string query)
    {
        await CreateAsync("draft", false);
        await CreateAsync("live", true);

        (await ListTitlesAsync("/api/announcements" + query)).Should().Equal("live");
    }

    [Theory]
    [InlineData("?publishedOnly=maybe", "maybe")]
    [InlineData("?publishedOnly=%20", " ")]
    [InlineData("?publishedOnly=x&publishedOnly=y", "x,y")]
    public async Task List_invalid_boolean_returns_java_api_error(string query, string raw)
    {
        using var response = await _client.GetAsync(Uri("/api/announcements" + query));

        await ShouldBeApiErrorAsync(response, HttpStatusCode.BadRequest, "Bad Request", $"Invalid boolean value [{raw}]");
    }

    [Fact]
    public async Task Get_returns_row_and_accepts_java_long_forms()
    {
        await CreateAsync("only", false);

        foreach (var id in new[] { "1", "+1", "01", "0x1" })
        {
            using var response = await _client.GetAsync(Uri("/api/announcements/" + id));
            response.StatusCode.Should().Be(HttpStatusCode.OK);
            using var json = await ReadJsonAsync(response);
            json.RootElement.GetProperty("title").GetString().Should().Be("only");
        }
    }

    [Theory]
    [InlineData("999")]
    [InlineData("-1")]
    public async Task Get_missing_returns_java_not_found(string id)
    {
        using var response = await _client.GetAsync(Uri("/api/announcements/" + id));

        await ShouldBeApiErrorAsync(response, HttpStatusCode.NotFound, "Not Found", $"announcement {id} not found");
    }

    [Theory]
    [InlineData("abc", "abc")]
    [InlineData("1.5", "1.5")]
    [InlineData("9223372036854775808", "9223372036854775808")]
    public async Task Get_unparsable_id_returns_for_input_string(string id, string raw)
    {
        using var response = await _client.GetAsync(Uri("/api/announcements/" + id));

        await ShouldBeApiErrorAsync(response, HttpStatusCode.BadRequest, "Bad Request", $"For input string: \"{raw}\"");
    }

    [Fact]
    public async Task Get_whitespace_id_returns_500_like_missing_path_variable()
    {
        using var response = await _client.GetAsync(Uri("/api/announcements/%20"));

        await ShouldBeSpringErrorAsync(response, HttpStatusCode.InternalServerError, "Internal Server Error", "/api/announcements/%20");
    }

    [Fact]
    public async Task Publish_flips_draft_and_returns_200()
    {
        await CreateAsync("draft", false);

        using var response = await _client.PostAsync(Uri("/api/announcements/1/publish"), null);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        using var json = await ReadJsonAsync(response);
        json.RootElement.GetProperty("id").GetInt64().Should().Be(1);
        json.RootElement.GetProperty("published").GetBoolean().Should().BeTrue();
        (await ListTitlesAsync("/api/announcements")).Should().Equal("draft");
    }

    [Fact]
    public async Task Publish_missing_returns_404_and_bad_id_returns_400()
    {
        using var missing = await _client.PostAsync(Uri("/api/announcements/77/publish"), null);
        await ShouldBeApiErrorAsync(missing, HttpStatusCode.NotFound, "Not Found", "announcement 77 not found");

        using var bad = await _client.PostAsync(Uri("/api/announcements/x1/publish"), null);
        await ShouldBeApiErrorAsync(bad, HttpStatusCode.BadRequest, "Bad Request", "For input string: \"x1\"");
    }

    [Theory]
    [InlineData("DELETE", "/api/announcements/1")]
    [InlineData("PUT", "/api/announcements")]
    [InlineData("PATCH", "/api/announcements/1")]
    [InlineData("POST", "/api/announcements/1")]
    [InlineData("GET", "/api/announcements/1/publish")]
    [InlineData("DELETE", "/api/announcements")]
    public async Task Unsupported_methods_return_405(string method, string path)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), Uri(path));

        using var response = await _client.SendAsync(request);

        await ShouldBeSpringErrorAsync(response, HttpStatusCode.MethodNotAllowed, "Method Not Allowed", path);
    }

    [Theory]
    [InlineData("GET", "/API/announcements")]
    [InlineData("GET", "/api/Announcements/1")]
    [InlineData("POST", "/api/announcements/1/PUBLISH")]
    public async Task Routes_are_case_sensitive_like_spring(string method, string path)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), Uri(path));

        using var response = await _client.SendAsync(request);

        await ShouldBeSpringErrorAsync(response, HttpStatusCode.NotFound, "Not Found", path);
    }

    [Fact]
    public async Task Schema_initializer_is_registered_and_skips_in_memory()
    {
        using var scope = _factory.Services.CreateScope();
        var initializers = scope.ServiceProvider.GetServices<ISchemaInitializer>();
        var initializer = initializers.OfType<AnnouncementsSchemaInitializer>().Should().ContainSingle().Subject;

        await initializer.Invoking(i => i.InitializeAsync(CancellationToken.None)).Should().NotThrowAsync();
    }

    private static Uri Uri(string path) => new(path, UriKind.Relative);

    private static async Task<JsonDocument> ReadJsonAsync(HttpResponseMessage response) =>
        JsonDocument.Parse(await response.Content.ReadAsStringAsync());

    private static async Task ShouldBeSpringErrorAsync(HttpResponseMessage response, HttpStatusCode status, string error, string path)
    {
        response.StatusCode.Should().Be(status);
        using var json = await ReadJsonAsync(response);
        json.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal("timestamp", "status", "error", "path");
        json.RootElement.GetProperty("status").GetInt32().Should().Be((int)status);
        json.RootElement.GetProperty("error").GetString().Should().Be(error);
        json.RootElement.GetProperty("path").GetString().Should().Be(path);
    }

    private static async Task ShouldBeApiErrorAsync(HttpResponseMessage response, HttpStatusCode status, string error, string message)
    {
        response.StatusCode.Should().Be(status);
        (await response.Content.ReadAsStringAsync()).Should().Be(JsonSerializer.Serialize(new { error, message }, SpringJson.CreateOptions()));
    }

    private async Task<HttpResponseMessage> PostJsonAsync(string path, string body)
    {
        using var content = new StringContent(body, Encoding.UTF8);
        content.Headers.ContentType = new MediaTypeHeaderValue("application/json");
        return await _client.PostAsync(Uri(path), content);
    }

    private async Task CreateAsync(string title, bool published)
    {
        using var response = await PostJsonAsync(
            "/api/announcements", JsonSerializer.Serialize(new { title, body = title + " body", published }));
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        await Task.Delay(2);
    }

    private async Task<List<string?>> ListTitlesAsync(string path)
    {
        using var response = await _client.GetAsync(Uri(path));
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        using var json = await ReadJsonAsync(response);
        return json.RootElement.EnumerateArray().Select(e => e.GetProperty("title").GetString()).ToList();
    }
}
