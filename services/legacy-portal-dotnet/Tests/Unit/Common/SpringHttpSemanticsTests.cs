using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Routing.Patterns;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.Unit.Common;

public class SpringHttpSemanticsTests : IClassFixture<InMemoryPortalFactory>
{
    private readonly InMemoryPortalFactory _factory;

    public SpringHttpSemanticsTests(InMemoryPortalFactory factory)
    {
        _factory = factory;
    }

    [Theory]
    [InlineData("/HEALTH")]
    [InlineData("/Actuator/health")]
    [InlineData("/API/announcements")]
    [InlineData("/api/Announcements/1")]
    [InlineData("/API/preferences/alice")]
    [InlineData("/api/Feedback?userId=alice")]
    [InlineData("/api/feedback/Average-Rating")]
    public async Task Route_literals_are_case_sensitive(string path)
    {
        using var client = _factory.CreateClient();

        using var response = await client.GetAsync(new Uri(path, UriKind.Relative));

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        body.RootElement.GetProperty("status").GetInt32().Should().Be(404);
        body.RootElement.GetProperty("path").GetString().Should().Be(path.Split('?')[0]);
    }

    [Theory]
    [InlineData("/health")]
    [InlineData("/api/preferences/MixedCaseUser")]
    public async Task Exact_case_paths_still_match(string path)
    {
        using var client = _factory.CreateClient();

        using var response = await client.GetAsync(new Uri(path, UriKind.Relative));

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Theory]
    [InlineData("application/xml")]
    [InlineData("text/plain")]
    public async Task Non_json_accept_returns_406_without_body(string accept)
    {
        using var client = _factory.CreateClient();
        using var request = new HttpRequestMessage(HttpMethod.Get, new Uri("/health", UriKind.Relative));
        request.Headers.Accept.ParseAdd(accept);

        using var response = await client.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.NotAcceptable);
        (await response.Content.ReadAsStringAsync()).Should().BeEmpty();
    }

    [Fact]
    public async Task Browser_accept_header_still_gets_json()
    {
        using var client = _factory.CreateClient();
        using var request = new HttpRequestMessage(HttpMethod.Get, new Uri("/health", UriKind.Relative));
        request.Headers.Accept.ParseAdd("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");

        using var response = await client.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
    }

    [Fact]
    public async Task Latin1_request_body_is_decoded()
    {
        using var client = _factory.CreateClient();
        using var content = new ByteArrayContent(Encoding.Latin1.GetBytes("{\"title\":\"caf\u00e9\",\"body\":\"b\"}"));
        content.Headers.ContentType = MediaTypeHeaderValue.Parse("application/json;charset=ISO-8859-1");

        using var response = await client.PostAsync(new Uri("/api/announcements", UriKind.Relative), content);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        body.RootElement.GetProperty("title").GetString().Should().Be("caf\u00e9");
    }

    [Theory]
    [InlineData("{\"title\":\"t\",\"body\":\"b\"} xyz")]
    [InlineData("{\"title\":\"t\",\"body\":\"b\"}{\"title\":\"ignored\"}")]
    public async Task Trailing_content_after_first_json_value_is_ignored(string json)
    {
        using var client = _factory.CreateClient();
        using var content = new StringContent(json, Encoding.UTF8, "application/json");

        using var response = await client.PostAsync(new Uri("/api/announcements", UriKind.Relative), content);

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        body.RootElement.GetProperty("title").GetString().Should().Be("t");
    }

    [Theory]
    [InlineData("")]
    [InlineData("{\"title\":")]
    [InlineData("xyz")]
    public void DeserializeFirstValue_rejects_missing_or_malformed_json(string json)
    {
        var act = () => SpringJsonInputFormatter.DeserializeFirstValue(Encoding.UTF8.GetBytes(json), typeof(Dictionary<string, string>), new JsonSerializerOptions());

        act.Should().Throw<JsonException>();
    }

    [Fact]
    public void DeserializeFirstValue_skips_utf8_bom()
    {
        var bytes = Encoding.UTF8.GetPreamble().Concat(Encoding.UTF8.GetBytes("{\"a\":\"b\"}")).ToArray();

        var result = SpringJsonInputFormatter.DeserializeFirstValue(bytes, typeof(Dictionary<string, string>), new JsonSerializerOptions());

        result.Should().BeEquivalentTo(new Dictionary<string, string> { ["a"] = "b" });
    }

    [Theory]
    [InlineData("/api/feedback/average-rating", "api/feedback/average-rating", true)]
    [InlineData("/api/feedback/Average-Rating", "api/feedback/average-rating", false)]
    [InlineData("/api/preferences/AnyCase", "api/preferences/{userId}", true)]
    [InlineData("/Api/preferences/x", "api/preferences/{userId}", false)]
    [InlineData("/api/announcements/", "api/announcements", true)]
    public void LiteralSegmentsMatch_compares_only_literal_segments_ordinally(string path, string template, bool expected)
    {
        CaseSensitiveRoutingMiddleware.LiteralSegmentsMatch(path, RoutePatternFactory.Parse(template)).Should().Be(expected);
    }
}
