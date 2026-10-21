using Microsoft.AspNetCore.Routing.Patterns;

namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// ASP.NET matches route literals case-insensitively; Spring MVC does not. A request whose path differs from the
/// matched route's literal segments only by case loses its endpoint, so it ends as Spring's 404.
/// </summary>
public sealed class CaseSensitiveRoutingMiddleware
{
    private readonly RequestDelegate next;

    public CaseSensitiveRoutingMiddleware(RequestDelegate next)
    {
        this.next = next;
    }

    public Task InvokeAsync(HttpContext context)
    {
        ArgumentNullException.ThrowIfNull(context);
        if (context.GetEndpoint() is RouteEndpoint endpoint
            && !LiteralSegmentsMatch(context.Request.Path.Value ?? string.Empty, endpoint.RoutePattern))
        {
            context.SetEndpoint(null);
            context.Request.RouteValues.Clear();
        }

        return next(context);
    }

    public static bool LiteralSegmentsMatch(string path, RoutePattern pattern)
    {
        ArgumentNullException.ThrowIfNull(pattern);
        var pathSegments = path.Split('/', StringSplitOptions.RemoveEmptyEntries);
        for (var i = 0; i < pattern.PathSegments.Count && i < pathSegments.Length; i++)
        {
            var parts = pattern.PathSegments[i].Parts;
            if (parts.Count == 1 && parts[0] is RoutePatternLiteralPart literal
                && !string.Equals(literal.Content, pathSegments[i], StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }
}
