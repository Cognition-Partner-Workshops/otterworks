using System.Net;

namespace DealerPortal.Bff.Tests;

[Collection(BffCollection.Name)]
public sealed class HostingTests
{
    [Fact]
    public async Task Session_WorksWithoutPortalKeyEvenWhenConfigured()
    {
        using var factory = new PortalFactory(new() { ["Portal:ClientKey"] = "test-client-key" });
        var client = factory.CreateClient();

        Assert.Equal(HttpStatusCode.OK, (await client.PostAsync("/bff/session", JsonBody("{\"email\":\"dealer-ops@dealer.example\",\"password\":\"x\"}"))).StatusCode);
    }

    [Fact]
    public async Task ServesTheAngularBuildWithClientSideRouting()
    {
        var root = Directory.CreateTempSubdirectory("dp-static-").FullName;
        await File.WriteAllTextAsync(Path.Combine(root, "index.html"), "<dp-root></dp-root>");
        await File.WriteAllTextAsync(Path.Combine(root, "main.js"), "console.log('portal');");
        try
        {
            using var factory = new PortalFactory(new() { ["Portal:StaticRoot"] = root });
            var client = factory.CreateClient();

            Assert.Contains("<dp-root>", await client.GetStringAsync("/"));
            Assert.Contains("<dp-root>", await client.GetStringAsync("/inventory/1VSLA0000AA000001"));
            Assert.Contains("portal", await client.GetStringAsync("/main.js"));
            Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/bff/unknown")).StatusCode);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact]
    public async Task HealthEndpointResponds()
    {
        using var factory = new PortalFactory();
        Assert.Equal(HttpStatusCode.OK, (await factory.CreateClient().GetAsync("/healthz")).StatusCode);
    }

    [Theory]
    [InlineData("Platform:Signing:CurrentKeyId", "")]
    [InlineData("Platform:Signing:CurrentKeyId", "vsl-synthetic-missing")]
    [InlineData("Platform:Signing:Keys:0:Material", "AA==")]
    [InlineData("Platform:Signing:Keys:0:Material", "invalid!")]
    public void StartupRejectsMissingOrInvalidKeys(string setting, string value)
    {
        using var factory = new PortalFactory(new() { [setting] = value });
        var error = Assert.Throws<InvalidOperationException>(() => factory.CreateClient());
        Assert.Contains("Platform:Signing", error.Message);
    }

    private static StringContent JsonBody(string json) => new(json, System.Text.Encoding.UTF8, "application/json");
}
