using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Announcements.Controllers;

/// <summary>
/// ASP.NET route templates match case-insensitively; Spring MVC does not. Requests whose path differs from the
/// controller prefix (or a literal segment of the action template) only by case get Spring's 404 body.
/// </summary>
[AttributeUsage(AttributeTargets.Class, AllowMultiple = false)]
public sealed class CaseSensitiveRouteAttribute : Attribute, IResourceFilter
{
    public CaseSensitiveRouteAttribute(string prefix)
    {
        Prefix = prefix;
    }

    public string Prefix { get; }

    public void OnResourceExecuting(ResourceExecutingContext context)
    {
        ArgumentNullException.ThrowIfNull(context);
        var path = context.HttpContext.Request.Path.Value ?? string.Empty;
        var template = context.ActionDescriptor.AttributeRouteInfo?.Template ?? string.Empty;
        if (!path.StartsWith(Prefix, StringComparison.Ordinal) || !LiteralSegmentsMatch(path, template))
        {
            var timeProvider = context.HttpContext.RequestServices.GetRequiredService<TimeProvider>();
            context.Result = new ObjectResult(
                ErrorResponses.SpringError(context.HttpContext, StatusCodes.Status404NotFound, timeProvider))
            {
                StatusCode = StatusCodes.Status404NotFound,
            };
        }
    }

    public void OnResourceExecuted(ResourceExecutedContext context)
    {
    }

    private static bool LiteralSegmentsMatch(string path, string template)
    {
        var pathSegments = path.Split('/', StringSplitOptions.RemoveEmptyEntries);
        var templateSegments = template.Split('/', StringSplitOptions.RemoveEmptyEntries);
        for (var i = 0; i < templateSegments.Length && i < pathSegments.Length; i++)
        {
            var segment = templateSegments[i];
            if (!segment.StartsWith('{') && !string.Equals(segment, pathSegments[i], StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }
}
