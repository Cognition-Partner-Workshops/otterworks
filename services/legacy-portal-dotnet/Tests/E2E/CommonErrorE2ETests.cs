using System.Net;
using System.Text.Json;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.E2E;

public class CommonErrorE2ETests : IClassFixture<InMemoryPortalFactory>
{
    private readonly InMemoryPortalFactory _factory;

    public CommonErrorE2ETests(InMemoryPortalFactory factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task Unknown_route_returns_spring_default_error_body()
    {
        using var client = _factory.CreateClient();

        using var response = await client.GetAsync(new Uri("/does-not-exist", UriKind.Relative));

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        body.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal("timestamp", "status", "error", "path");
        body.RootElement.GetProperty("status").GetInt32().Should().Be(404);
        body.RootElement.GetProperty("error").GetString().Should().Be("Not Found");
        body.RootElement.GetProperty("path").GetString().Should().Be("/does-not-exist");
        response.Headers.GetValues("X-Frame-Options").Should().Equal("DENY");
    }
}
