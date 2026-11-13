using System.Net;
using System.Text;
using Platform.Shared.Http;

namespace Platform.Shared.Tests;

[Collection(SafeHttpCollection.Name)]
public class SafeHttpTests
{
    [Fact]
    public async Task Fetch_ReturnsBodyStatusAndContentType()
    {
        var stub = new StubHandler(_ => StubHandler.Ok("{\"ok\":true}", "application/json"));
        SafeHttp.UseHandler(stub);

        var result = await SafeHttp.Fetch("https://images.dealer.example/cars/42.json");

        Assert.True(result.IsSuccess);
        Assert.Equal(HttpStatusCode.OK, result.StatusCode);
        Assert.Equal("application/json", result.ContentType);
        Assert.Equal("{\"ok\":true}", Encoding.UTF8.GetString(result.Body));
        Assert.Equal(new Uri("https://images.dealer.example/cars/42.json"), Assert.Single(stub.Requests));
    }

    [Theory]
    [InlineData("not a url")]
    [InlineData("/relative/path")]
    [InlineData("file:///etc/hosts")]
    [InlineData("ftp://files.dealer.example/a.png")]
    public async Task Fetch_RejectsNonHttpUrls(string url)
    {
        SafeHttp.UseHandler(new StubHandler(_ => StubHandler.Ok("unused")));

        await Assert.ThrowsAsync<ArgumentException>(() => SafeHttp.Fetch(url));
    }

    [Fact]
    public async Task Fetch_RejectsOversizedResponses()
    {
        var big = new string('x', SafeHttp.MaxResponseBytes + 1);
        SafeHttp.UseHandler(new StubHandler(_ => StubHandler.Ok(big)));

        await Assert.ThrowsAsync<InvalidOperationException>(() => SafeHttp.Fetch("https://images.dealer.example/big"));
    }
}

[CollectionDefinition(Name, DisableParallelization = true)]
public sealed class SafeHttpCollection
{
    public const string Name = "SafeHttp shared transport";
}
