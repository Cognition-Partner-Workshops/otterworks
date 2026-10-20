using System.Security.Claims;
using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

namespace OtterWorks.AuditService.Security;

/// <summary>
/// Caller identity and authorization rules for the audit API. The auth-service issues HMAC-signed
/// JWTs with the user id in <c>sub</c>, the role names in <c>roles</c> and <c>type: access</c>;
/// the api-gateway forwards the bearer token unchanged, so the service validates it itself instead
/// of trusting request parameters or forwarded headers for identity.
/// </summary>
public static class AuditAuthorization
{
    public const string AdminRole = "ADMIN";
    public const string AdminPolicy = "AuditAdmin";
    public const string SubjectClaim = "sub";
    public const string RolesClaim = "roles";
    public const string TokenTypeClaim = "type";
    public const string AccessTokenType = "access";

    public static TokenValidationParameters TokenValidationParameters(string jwtSecret) => new()
    {
        ValidateIssuerSigningKey = true,
        IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSecret)),
        ValidAlgorithms = new[]
        {
            SecurityAlgorithms.HmacSha256,
            SecurityAlgorithms.HmacSha384,
            SecurityAlgorithms.HmacSha512,
        },
        ValidateIssuer = false,
        ValidateAudience = false,
        ValidateLifetime = true,
        RequireExpirationTime = true,
        NameClaimType = SubjectClaim,
        RoleClaimType = RolesClaim,
    };

    public static void ConfigureJwtBearer(JwtBearerOptions options, string jwtSecret)
    {
        options.MapInboundClaims = false;
        options.TokenValidationParameters = TokenValidationParameters(jwtSecret);
        options.Events = new JwtBearerEvents
        {
            OnTokenValidated = context =>
            {
                if (!IsAccessToken(context.Principal))
                {
                    context.Fail("Token is not an access token.");
                }
                return Task.CompletedTask;
            },
        };
    }

    /// <summary>Refresh tokens are signed with the same key; only <c>type: access</c> grants API access.</summary>
    public static bool IsAccessToken(ClaimsPrincipal? principal) =>
        string.Equals(principal?.FindFirstValue(TokenTypeClaim), AccessTokenType, StringComparison.Ordinal) &&
        !string.IsNullOrWhiteSpace(UserId(principal));

    public static string? UserId(ClaimsPrincipal? principal) => principal?.FindFirstValue(SubjectClaim);

    public static bool IsAdmin(ClaimsPrincipal? principal) => principal?.IsInRole(AdminRole) ?? false;

    /// <summary>A caller may read audit data about themselves; only admins may read other users' data.</summary>
    public static bool CanReadUser(ClaimsPrincipal principal, string? subjectUserId)
    {
        if (IsAdmin(principal))
        {
            return true;
        }

        var callerId = UserId(principal);
        return !string.IsNullOrWhiteSpace(callerId) &&
               string.Equals(callerId, subjectUserId, StringComparison.Ordinal);
    }
}
