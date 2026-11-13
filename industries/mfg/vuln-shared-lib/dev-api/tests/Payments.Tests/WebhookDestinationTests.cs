using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using Payments.Models;
using Payments.Services;

namespace Payments.Tests;

public sealed class WebhookDestinationTests
{
    [Theory]
    [Trait("Category","Security")]
    [InlineData("10.0.0.5")]
    [InlineData(null)]
    public async Task HostResolvingToPrivateOrNoAddressIsRejected(string? address)
    {
        using var factory = new PaymentsApiFactory
        {
            WebhookAddresses = address is null ? [] : [IPAddress.Parse(address)]
        };
        using var client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
        var response = await client.PostAsJsonAsync("/api/payments/webhooks/test",
            new WebhookTestRequest("https://subscriber.dealer.example/events"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Null(factory.Transport.Destination);
    }

    [Theory]
    [Trait("Category","Security")]
    [InlineData("0.0.0.0")]
    [InlineData("100.64.0.1")]
    [InlineData("100.127.255.255")]
    [InlineData("172.16.0.1")]
    [InlineData("192.168.0.1")]
    [InlineData("169.254.169.254")]
    [InlineData("224.0.0.1")]
    [InlineData("192.0.0.1")]
    [InlineData("192.0.2.1")]
    [InlineData("198.18.0.1")]
    [InlineData("198.19.255.255")]
    [InlineData("198.51.100.1")]
    [InlineData("203.0.113.1")]
    [InlineData("192.88.99.1")]
    [InlineData("255.255.255.255")]
    [InlineData("2001:db8::1")]
    [InlineData("64:ff9b::a00:1")]
    [InlineData("64:ff9b::c612:1")]
    [InlineData("::ffff:198.18.0.1")]
    [InlineData("::")]
    [InlineData("fc00::1")]
    [InlineData("fe80::1")]
    [InlineData("ff02::1")]
    [InlineData("::ffff:127.0.0.1")]
    [InlineData("::ffff:10.0.0.1")]
    public void NonPublicAddressesAreRejected(string address) =>
        Assert.False(WebhookDestinationPolicy.IsPublic(IPAddress.Parse(address)));

    [Theory]
    [Trait("Category","Security")]
    [InlineData("93.184.216.34")]
    [InlineData("2606:4700:4700::1111")]
    [InlineData("64:ff9b::5db8:d822")]
    public void PublicAddressesAreAccepted(string address) =>
        Assert.True(WebhookDestinationPolicy.IsPublic(IPAddress.Parse(address)));
}
