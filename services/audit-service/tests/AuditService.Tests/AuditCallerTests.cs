using Microsoft.AspNetCore.Http;
using OtterWorks.AuditService.Middleware;
using Xunit;

namespace OtterWorks.AuditService.Tests;

public class AuditCallerTests
{
    private const string Token = "internal-token";

    private static AuditCaller Resolve(params (string Name, string Value)[] headers)
    {
        var context = new DefaultHttpContext();
        foreach (var (name, value) in headers)
        {
            context.Request.Headers[name] = value;
        }

        return AuditCaller.Resolve(context, Token);
    }

    [Fact]
    public void NoIdentity_IsNotAuthenticated()
    {
        var caller = Resolve();
        Assert.False(caller.IsAuthenticated);
        Assert.False(caller.IsPrivileged);
    }

    [Fact]
    public void GatewayUser_IsAuthenticatedButNotPrivileged()
    {
        var caller = Resolve((AuditCaller.UserIdHeader, "user-1"), (AuditCaller.UserRolesHeader, "user"));
        Assert.True(caller.IsAuthenticated);
        Assert.False(caller.IsPrivileged);
        Assert.Equal("user-1", caller.UserId);
    }

    [Theory]
    [InlineData("admin")]
    [InlineData("ROLE_ADMIN")]
    [InlineData("user,compliance")]
    public void AdminOrComplianceRole_IsPrivileged(string roles)
    {
        var caller = Resolve((AuditCaller.UserIdHeader, "user-1"), (AuditCaller.UserRolesHeader, roles));
        Assert.True(caller.IsPrivileged);
    }

    [Fact]
    public void RolesWithoutUser_AreIgnored()
    {
        var caller = Resolve((AuditCaller.UserRolesHeader, "admin"));
        Assert.False(caller.IsAuthenticated);
        Assert.False(caller.IsPrivileged);
    }

    [Fact]
    public void ServiceToken_IsInternal()
    {
        var caller = Resolve((AuditCaller.ServiceTokenHeader, Token));
        Assert.True(caller.IsInternal);
        Assert.True(caller.IsPrivileged);
    }

    [Fact]
    public void WrongServiceToken_IsNotInternal()
    {
        var caller = Resolve((AuditCaller.ServiceTokenHeader, "guess"));
        Assert.False(caller.IsInternal);
        Assert.False(caller.IsAuthenticated);
    }

    [Fact]
    public void UnconfiguredToken_NeverMatches()
    {
        var context = new DefaultHttpContext();
        context.Request.Headers[AuditCaller.ServiceTokenHeader] = string.Empty;
        Assert.False(AuditCaller.Resolve(context, string.Empty).IsInternal);
    }
}
