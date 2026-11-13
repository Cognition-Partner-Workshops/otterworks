using Identity.Models;
using Identity.Services;
using Platform.Shared.Crypto;
using System.Security.Cryptography;

namespace Identity.Tests;

public sealed class AccountServicesTests
{
    [Theory]
    [InlineData("ops@dealer.example")]
    [InlineData("")]
    public void RememberCookiesAreRandomizedAndRoundTrip(string email)
    {
        var service = new RememberMeService();
        var cookie = service.Create(email);
        Assert.NotEqual(cookie, service.Create(email));
        Assert.Equal(email, service.Read(cookie));
    }

    [Fact]
    public void RememberCookiesRejectTampering()
    {
        var service = new RememberMeService();
        var bytes = Base64Url.Decode(service.Create("ops@dealer.example"));
        bytes[^1] ^= 1;
        Assert.Throws<CryptographicException>(() => service.Read(Base64Url.Encode(bytes)));
    }

    [Fact]
    public void TokenRoundTripPreservesAccount()
    {
        var service = new AccessTokenService(new AccountClock(), TestConfiguration.SyntheticSigning.Provider);
        var token = service.Create(new Account { Email = "ops@dealer.example", DealerId = "D-1001", Roles = "dealer,manager" });
        var identity = service.Verify(token.AccessToken);
        Assert.Equal("ops@dealer.example", identity!.Email);
        Assert.Equal(new[] { "dealer", "manager" }, identity.Roles);
        Assert.Null(service.Verify(token.AccessToken + "a"));
        Assert.Null(service.Verify(""));
    }

    [Fact]
    public void ResetTokensRoundTripAndDiffer()
    {
        var service = new ResetTokenService();
        var first = service.Create("ops@dealer.example");
        Assert.StartsWith("ops@dealer.example:", service.Read(first));
        Assert.NotEqual(first, service.Create("ops@dealer.example"));
    }
}
