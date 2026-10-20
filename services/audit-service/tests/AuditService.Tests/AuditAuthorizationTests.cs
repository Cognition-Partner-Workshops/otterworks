using System.Security.Claims;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;
using OtterWorks.AuditService.Security;

namespace AuditService.Tests;

public class AuditAuthorizationTests
{
    // 64 bytes, like the `openssl rand -hex 32` value the deploy scripts mint (HS512 needs >= 64).
    private static readonly string Secret = new('k', 64);
    private static readonly string OtherSecret = new('x', 64);

    private static ClaimsPrincipal Principal(string userId, params string[] roles)
    {
        var claims = new List<Claim>
        {
            new(AuditAuthorization.SubjectClaim, userId),
            new(AuditAuthorization.TokenTypeClaim, AuditAuthorization.AccessTokenType),
        };
        claims.AddRange(roles.Select(r => new Claim(AuditAuthorization.RolesClaim, r)));
        var identity = new ClaimsIdentity(claims, "test", AuditAuthorization.SubjectClaim, AuditAuthorization.RolesClaim);
        return new ClaimsPrincipal(identity);
    }

    private static string SignToken(string secret, string algorithm, IDictionary<string, object> claims, DateTime? expires = null)
    {
        var handler = new JsonWebTokenHandler();
        return handler.CreateToken(new SecurityTokenDescriptor
        {
            Claims = claims,
            Expires = expires ?? DateTime.UtcNow.AddMinutes(5),
            SigningCredentials = new SigningCredentials(
                new SymmetricSecurityKey(System.Text.Encoding.UTF8.GetBytes(secret)), algorithm),
        });
    }

    private static async Task<TokenValidationResult> Validate(string token, string secret) =>
        await new JsonWebTokenHandler().ValidateTokenAsync(token, AuditAuthorization.TokenValidationParameters(secret));

    private static Dictionary<string, object> AccessClaims(string userId, params string[] roles) => new()
    {
        ["sub"] = userId,
        ["roles"] = roles,
        ["type"] = "access",
    };

    [Theory]
    [InlineData(SecurityAlgorithms.HmacSha256)]
    [InlineData(SecurityAlgorithms.HmacSha384)]
    [InlineData(SecurityAlgorithms.HmacSha512)]
    public async Task ValidToken_IsAccepted_WithSubjectAndRoles(string algorithm)
    {
        var token = SignToken(Secret, algorithm, AccessClaims("user-1", "USER", "ADMIN"));

        var result = await Validate(token, Secret);

        Assert.True(result.IsValid, result.Exception?.Message);
        var principal = new ClaimsPrincipal(result.ClaimsIdentity);
        Assert.True(AuditAuthorization.IsAccessToken(principal));
        Assert.Equal("user-1", AuditAuthorization.UserId(principal));
        Assert.True(AuditAuthorization.IsAdmin(principal));
    }

    [Fact]
    public async Task TokenSignedWithOtherSecret_IsRejected()
    {
        var token = SignToken(OtherSecret, SecurityAlgorithms.HmacSha256, AccessClaims("victim"));

        var result = await Validate(token, Secret);

        Assert.False(result.IsValid);
    }

    [Fact]
    public async Task ExpiredToken_IsRejected()
    {
        var token = SignToken(Secret, SecurityAlgorithms.HmacSha256, AccessClaims("user-1"), DateTime.UtcNow.AddHours(-1));

        var result = await Validate(token, Secret);

        Assert.False(result.IsValid);
    }

    [Fact]
    public async Task RefreshToken_IsNotAnAccessToken()
    {
        var token = SignToken(Secret, SecurityAlgorithms.HmacSha384, new Dictionary<string, object>
        {
            ["sub"] = "user-1",
            ["type"] = "refresh",
        });

        var result = await Validate(token, Secret);

        Assert.True(result.IsValid);
        Assert.False(AuditAuthorization.IsAccessToken(new ClaimsPrincipal(result.ClaimsIdentity)));
    }

    [Fact]
    public void TokenWithoutSubject_IsNotAnAccessToken()
    {
        var identity = new ClaimsIdentity(new[] { new Claim("type", "access") }, "test");
        Assert.False(AuditAuthorization.IsAccessToken(new ClaimsPrincipal(identity)));
    }

    [Fact]
    public void User_CanReadOwnData_Only()
    {
        var user = Principal("user-1", "USER");

        Assert.True(AuditAuthorization.CanReadUser(user, "user-1"));
        Assert.False(AuditAuthorization.CanReadUser(user, "user-2"));
        Assert.False(AuditAuthorization.CanReadUser(user, null));
        Assert.False(AuditAuthorization.IsAdmin(user));
    }

    [Fact]
    public void Admin_CanReadAnyUser()
    {
        var admin = Principal("admin-1", "USER", "ADMIN");

        Assert.True(AuditAuthorization.IsAdmin(admin));
        Assert.True(AuditAuthorization.CanReadUser(admin, "user-2"));
    }

    [Fact]
    public void RoleCheck_IsCaseSensitive_AndIgnoresLookalikes()
    {
        Assert.False(AuditAuthorization.IsAdmin(Principal("user-1", "admin")));
        Assert.False(AuditAuthorization.IsAdmin(Principal("user-1", "ADMINISTRATOR")));
        Assert.False(AuditAuthorization.IsAdmin(new ClaimsPrincipal(new ClaimsIdentity())));
    }
}
