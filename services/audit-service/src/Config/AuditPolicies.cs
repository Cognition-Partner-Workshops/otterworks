using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

namespace OtterWorks.AuditService.Config;

/// <summary>
/// Who may read or administer the audit log. Roles come from the verified JWT's "roles"
/// claim (auth-service issues ADMIN/USER; AUDITOR is reserved for compliance reviewers;
/// SERVICE is the short-lived token internal services such as report-service mint with
/// the shared secret).
/// </summary>
public static class AuditPolicies
{
    public const string Reader = "AuditReader";
    public const string Admin = "AuditAdmin";

    public const string RolesClaim = "roles";
    public const string TokenTypeClaim = "type";
    public const string RefreshTokenType = "refresh";

    public static readonly string[] ReaderRoles = { "ADMIN", "AUDITOR", "SERVICE" };
    public static readonly string[] AdminRoles = { "ADMIN" };

    public static IServiceCollection AddAuditAuthorization(this IServiceCollection services, JwtSettings jwt)
    {
        services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
            .AddJwtBearer(options =>
            {
                options.MapInboundClaims = false;
                options.TokenValidationParameters = new TokenValidationParameters
                {
                    IssuerSigningKey = jwt.SigningKey,
                    ValidAlgorithms = new[] { SecurityAlgorithms.HmacSha256, SecurityAlgorithms.HmacSha384, SecurityAlgorithms.HmacSha512 },
                    ValidateIssuerSigningKey = true,
                    ValidateIssuer = false,
                    ValidateAudience = false,
                    ValidateLifetime = true,
                    RequireExpirationTime = true,
                    ClockSkew = TimeSpan.FromSeconds(30),
                    RoleClaimType = RolesClaim,
                    NameClaimType = "sub",
                };
                options.Events = new JwtBearerEvents
                {
                    OnTokenValidated = context =>
                    {
                        var tokenType = context.Principal?.FindFirst(TokenTypeClaim)?.Value;
                        if (string.Equals(tokenType, RefreshTokenType, StringComparison.OrdinalIgnoreCase))
                        {
                            context.Fail("Refresh token cannot be used as access token");
                        }

                        return Task.CompletedTask;
                    },
                };
            });

        services.AddAuthorizationBuilder()
            .AddPolicy(Reader, policy => policy.RequireAuthenticatedUser().RequireRole(ReaderRoles))
            .AddPolicy(Admin, policy => policy.RequireAuthenticatedUser().RequireRole(AdminRoles));

        return services;
    }
}
