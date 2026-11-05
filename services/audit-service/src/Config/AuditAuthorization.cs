using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

namespace OtterWorks.AuditService.Config;

public static class AuditAuthorization
{
    public static void AddAuditAuthorization(this IServiceCollection services, IConfiguration configuration)
    {
        var secret = configuration["JWT_SECRET"];
        services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(options =>
        {
            options.MapInboundClaims = false;
            options.TokenValidationParameters = new TokenValidationParameters
            {
                ValidateIssuer = false,
                ValidateAudience = false,
                ValidateIssuerSigningKey = true,
                IssuerSigningKey = string.IsNullOrWhiteSpace(secret) ? null : new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret)),
                ValidAlgorithms = new[] { SecurityAlgorithms.HmacSha256, SecurityAlgorithms.HmacSha384 },
                ValidateLifetime = true,
                RequireExpirationTime = true,
                ClockSkew = TimeSpan.FromSeconds(30),
                NameClaimType = "sub",
                RoleClaimType = "roles",
            };
            options.Events = new JwtBearerEvents
            {
                OnTokenValidated = context =>
                {
                    if (string.IsNullOrWhiteSpace(context.Principal?.Identity?.Name) ||
                        context.Principal?.FindFirst("type")?.Value == "refresh")
                        context.Fail("Access token required");
                    return Task.CompletedTask;
                },
            };
        });
        services.AddAuthorization(options =>
        {
            options.AddPolicy("AuditRead", policy => policy.RequireAuthenticatedUser().RequireRole("ADMIN", "AUDITOR"));
            options.AddPolicy("AuditWrite", policy => policy.RequireAuthenticatedUser().RequireRole("SERVICE"));
            options.AddPolicy("AuditUserReport", policy => policy.RequireAuthenticatedUser().RequireAssertion(context =>
                context.User.IsInRole("ADMIN") || context.User.IsInRole("AUDITOR") ||
                context.Resource is HttpContext http &&
                context.User.Identity?.Name == http.Request.RouteValues["userId"]?.ToString()));
        });
    }
}
