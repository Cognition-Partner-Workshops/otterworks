using System.Net;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Moq;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Feedback.Services;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.Unit.Feedback;

public class FeedbackControllerTests : IClassFixture<InMemoryPortalFactory>
{
    private static readonly string[] FeedbackKeys = ["id", "userId", "rating", "message", "createdAt"];
    private static readonly string[] SpringErrorKeys = ["timestamp", "status", "error", "path"];

    private readonly InMemoryPortalFactory _factory;

    public FeedbackControllerTests(InMemoryPortalFactory factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task Post_returns_201_with_java_shaped_body()
    {
        using var client = _factory.CreateClient();
        var user = NewUser();

        using var response = await PostJsonAsync(client, $"{{\"userId\":\"{user}\",\"rating\":5,\"message\":\"great\"}}");

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        response.Headers.Location.Should().BeNull();
        using var body = await ReadJsonAsync(response);
        body.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal(FeedbackKeys);
        body.RootElement.GetProperty("id").GetInt64().Should().BePositive();
        body.RootElement.GetProperty("userId").GetString().Should().Be(user);
        body.RootElement.GetProperty("rating").GetInt32().Should().Be(5);
        body.RootElement.GetProperty("message").GetString().Should().Be("great");
        body.RootElement.GetProperty("createdAt").GetString().Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.(\d{3}|\d{6}))?Z$");
    }

    [Theory]
    [InlineData("\"4\"", 4)]
    [InlineData("4.7", 4)]
    [InlineData("1.0", 1)]
    [InlineData("\" 5 \"", 5)]
    public async Task Post_coerces_rating_like_jackson(string ratingJson, int expected)
    {
        using var client = _factory.CreateClient();

        using var response = await PostJsonAsync(client, $"{{\"userId\":\"{NewUser()}\",\"rating\":{ratingJson},\"message\":\"m\"}}");

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        using var body = await ReadJsonAsync(response);
        body.RootElement.GetProperty("rating").GetInt32().Should().Be(expected);
    }

    [Fact]
    public async Task Post_ignores_unknown_properties()
    {
        using var client = _factory.CreateClient();

        using var response = await PostJsonAsync(client, $"{{\"userId\":\"{NewUser()}\",\"rating\":2,\"message\":\"m\",\"extra\":true,\"id\":999}}");

        response.StatusCode.Should().Be(HttpStatusCode.Created);
        using var body = await ReadJsonAsync(response);
        body.RootElement.GetProperty("id").GetInt64().Should().NotBe(999);
    }

    [Theory]
    [InlineData("{\"userId\":\"u1\",\"rating\":9,\"message\":\"bad rating\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":0,\"message\":\"zero\"}")]
    [InlineData("{\"userId\":\"u1\",\"message\":\"rating omitted\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":null,\"message\":\"rating null\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":4,\"message\":\"\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":4,\"message\":\"   \"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":4}")]
    [InlineData("{\"userId\":\"\",\"rating\":4,\"message\":\"m\"}")]
    [InlineData("{\"rating\":4,\"message\":\"m\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":\"abc\",\"message\":\"m\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":10000000000,\"message\":\"m\"}")]
    [InlineData("{\"userId\":\"u1\",\"rating\":true,\"message\":\"m\"}")]
    [InlineData("{\"userId\":")]
    [InlineData("[]")]
    [InlineData("null")]
    public async Task Post_invalid_payload_returns_spring_400(string json)
    {
        using var client = _factory.CreateClient();

        using var response = await PostJsonAsync(client, json);

        await AssertSpringErrorAsync(response, HttpStatusCode.BadRequest, "Bad Request", "/api/feedback");
    }

    [Fact]
    public async Task Post_user_id_longer_than_100_returns_400_and_100_is_accepted()
    {
        using var client = _factory.CreateClient();

        using var tooLong = await PostJsonAsync(client, $"{{\"userId\":\"{new string('u', 101)}\",\"rating\":4,\"message\":\"m\"}}");
        using var atLimit = await PostJsonAsync(client, $"{{\"userId\":\"{new string('v', 100)}\",\"rating\":4,\"message\":\"m\"}}");

        await AssertSpringErrorAsync(tooLong, HttpStatusCode.BadRequest, "Bad Request", "/api/feedback");
        atLimit.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    [Fact]
    public async Task Post_message_longer_than_2000_returns_400()
    {
        using var client = _factory.CreateClient();

        using var response = await PostJsonAsync(client, $"{{\"userId\":\"u1\",\"rating\":4,\"message\":\"{new string('m', 2001)}\"}}");

        await AssertSpringErrorAsync(response, HttpStatusCode.BadRequest, "Bad Request", "/api/feedback");
    }

    [Fact]
    public async Task Post_text_plain_returns_spring_415()
    {
        using var client = _factory.CreateClient();
        using var content = new StringContent("rating=5", Encoding.UTF8, "text/plain");

        using var response = await client.PostAsync("/api/feedback", content);

        await AssertSpringErrorAsync(response, HttpStatusCode.UnsupportedMediaType, "Unsupported Media Type", "/api/feedback");
    }

    [Theory]
    [InlineData("DELETE")]
    [InlineData("PUT")]
    [InlineData("PATCH")]
    public async Task Unsupported_method_returns_spring_405(string method)
    {
        using var client = _factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), "/api/feedback");

        using var response = await client.SendAsync(request);

        await AssertSpringErrorAsync(response, HttpStatusCode.MethodNotAllowed, "Method Not Allowed", "/api/feedback");
    }

    [Fact]
    public async Task Get_without_user_id_returns_spring_400()
    {
        using var client = _factory.CreateClient();

        using var response = await client.GetAsync("/api/feedback?other=1");

        await AssertSpringErrorAsync(response, HttpStatusCode.BadRequest, "Bad Request", "/api/feedback");
    }

    [Fact]
    public async Task Get_with_empty_user_id_returns_empty_array()
    {
        using var client = _factory.CreateClient();

        using var response = await client.GetAsync("/api/feedback?userId=");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        (await response.Content.ReadAsStringAsync()).Should().Be("[]");
    }

    [Fact]
    public async Task Get_lists_only_that_users_feedback_newest_first()
    {
        using var client = _factory.CreateClient();
        var user = NewUser();
        var other = NewUser();
        var firstId = await SubmitAsync(client, user, 5, "first");
        await SubmitAsync(client, other, 1, "other");
        await Task.Delay(5);
        var secondId = await SubmitAsync(client, user, 3, "second");

        using var response = await client.GetAsync($"/api/feedback?userId={user}");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        using var body = await ReadJsonAsync(response);
        body.RootElement.EnumerateArray().Select(e => e.GetProperty("id").GetInt64()).Should().Equal(secondId, firstId);
        body.RootElement[0].EnumerateObject().Select(p => p.Name).Should().Equal(FeedbackKeys);
    }

    [Fact]
    public async Task Get_with_repeated_user_id_joins_values_like_spring()
    {
        var service = new Mock<IFeedbackService>();
        service.Setup(s => s.ListForUserAsync("a,b", It.IsAny<CancellationToken>())).ReturnsAsync([]);
        using var factory = WithService(service.Object);
        using var client = factory.CreateClient();

        using var response = await client.GetAsync("/api/feedback?userId=a&userId=b");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        service.Verify(s => s.ListForUserAsync("a,b", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task Average_rating_on_empty_table_is_zero_point_zero()
    {
        using var factory = new InMemoryPortalFactory();
        using var client = factory.CreateClient();

        using var response = await client.GetAsync("/api/feedback/average-rating");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        (await response.Content.ReadAsStringAsync()).Should().Be("{\"averageRating\":0.0}");
    }

    [Fact]
    public async Task Average_rating_serializes_like_java_doubles()
    {
        using var factory = new InMemoryPortalFactory();
        using var client = factory.CreateClient();
        await SubmitAsync(client, "u1", 5, "a");
        await SubmitAsync(client, "u1", 3, "b");
        await SubmitAsync(client, "u2", 1, "c");

        (await client.GetStringAsync("/api/feedback/average-rating")).Should().Be("{\"averageRating\":3.0}");

        await SubmitAsync(client, "u3", 4, "d");
        await SubmitAsync(client, "u3", 2, "e");
        await SubmitAsync(client, "u3", 4, "f");

        (await client.GetStringAsync("/api/feedback/average-rating?extra=1")).Should().Be("{\"averageRating\":3.1666666666666665}");
    }

    [Fact]
    public async Task Service_level_validation_maps_to_api_error_body()
    {
        var service = new Mock<IFeedbackService>();
        service
            .Setup(s => s.SubmitAsync(It.IsAny<string>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ThrowsAsync(new PortalValidationException("rating must be between 1 and 5"));
        using var factory = WithService(service.Object);
        using var client = factory.CreateClient();

        using var response = await PostJsonAsync(client, "{\"userId\":\"u1\",\"rating\":3,\"message\":\"m\"}");

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        (await response.Content.ReadAsStringAsync()).Should().Be("{\"error\":\"Bad Request\",\"message\":\"rating must be between 1 and 5\"}");
    }

    internal static async Task<HttpResponseMessage> PostJsonAsync(HttpClient client, string json)
    {
        using var content = new StringContent(json, Encoding.UTF8, "application/json");
        return await client.PostAsync("/api/feedback", content);
    }

    internal static async Task<JsonDocument> ReadJsonAsync(HttpResponseMessage response)
    {
        return JsonDocument.Parse(await response.Content.ReadAsStringAsync());
    }

    internal static async Task AssertSpringErrorAsync(HttpResponseMessage response, HttpStatusCode status, string error, string path)
    {
        response.StatusCode.Should().Be(status);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        using var body = await ReadJsonAsync(response);
        body.RootElement.EnumerateObject().Select(p => p.Name).Should().Equal(SpringErrorKeys);
        body.RootElement.GetProperty("timestamp").GetString().Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$");
        body.RootElement.GetProperty("status").GetInt32().Should().Be((int)status);
        body.RootElement.GetProperty("error").GetString().Should().Be(error);
        body.RootElement.GetProperty("path").GetString().Should().Be(path);
    }

    private static string NewUser() => $"user-{Guid.NewGuid():N}";

    private static async Task<long> SubmitAsync(HttpClient client, string userId, int rating, string message)
    {
        using var response = await PostJsonAsync(client, JsonSerializer.Serialize(new { userId, rating, message }));
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        using var body = await ReadJsonAsync(response);
        return body.RootElement.GetProperty("id").GetInt64();
    }

    private WebApplicationFactory<Program> WithService(IFeedbackService service)
    {
        return _factory.WithWebHostBuilder(b => b.ConfigureTestServices(s => s.AddScoped(_ => service)));
    }
}
