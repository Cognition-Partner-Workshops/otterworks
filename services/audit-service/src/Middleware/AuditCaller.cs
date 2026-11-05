using System.Security.Cryptography;
using System.Text;

namespace OtterWorks.AuditService.Middleware;

/// <summary>
/// Who is calling the audit API. Internal callers present the shared service
/// token (<c>AUDIT_SERVICE_TOKEN</c>); end users arrive through the api-gateway,
/// which forwards the validated JWT subject as <c>X-User-ID</c> and its roles as
/// <c>X-User-Roles</c> (and strips any client-supplied value for both).
/// </summary>
public sealed record AuditCaller(string? UserId, bool IsInternal, bool IsAdmin)
{
    public const string ServiceTokenHeader = "X-Service-Token";
    public const string UserIdHeader = "X-User-ID";
    public const string UserRolesHeader = "X-User-Roles";
    public const string TokenEnvVar = "AUDIT_SERVICE_TOKEN";

    private static readonly string[] AdminRoles = { "admin", "compliance" };

    public bool IsAuthenticated => IsInternal || !string.IsNullOrEmpty(UserId);

    /// <summary>Internal services and admin/compliance users may see the whole log.</summary>
    public bool IsPrivileged => IsInternal || IsAdmin;

    public static AuditCaller Resolve(HttpContext context, string? configuredToken)
    {
        var headers = context.Request.Headers;
        var internalCaller = TokenMatches(headers[ServiceTokenHeader].ToString(), configuredToken);

        var userId = headers[UserIdHeader].ToString().Trim();
        var roles = headers[UserRolesHeader].ToString()
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var isAdmin = !string.IsNullOrEmpty(userId) &&
            roles.Any(r => AdminRoles.Contains(r.ToLowerInvariant().Replace("role_", string.Empty)));

        return new AuditCaller(string.IsNullOrEmpty(userId) ? null : userId, internalCaller, isAdmin);
    }

    private static bool TokenMatches(string presented, string? configured)
    {
        if (string.IsNullOrEmpty(configured) || string.IsNullOrEmpty(presented))
        {
            return false;
        }

        return CryptographicOperations.FixedTimeEquals(
            Encoding.UTF8.GetBytes(presented), Encoding.UTF8.GetBytes(configured));
    }
}
