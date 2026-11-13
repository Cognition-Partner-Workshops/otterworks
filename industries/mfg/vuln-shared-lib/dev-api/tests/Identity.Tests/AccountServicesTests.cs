using Identity.Models;
using Identity.Services;

namespace Identity.Tests;

public sealed class AccountServicesTests
{
    [Fact]
    public void TokenRoundTripPreservesAccount()
    {
        var service = new AccessTokenService(new AccountClock());
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
