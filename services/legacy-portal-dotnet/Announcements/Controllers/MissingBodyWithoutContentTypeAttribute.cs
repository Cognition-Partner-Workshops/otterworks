using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Announcements.Controllers;

/// <summary>
/// Spring reads a <c>@RequestBody</c> without a Content-Type as <c>application/octet-stream</c>; when that body is
/// empty no converter is needed and it fails with "Required request body is missing" (400) rather than 415.
/// Runs before <see cref="ConsumesAttribute"/>, which would otherwise answer 415.
/// </summary>
[AttributeUsage(AttributeTargets.Method, AllowMultiple = false)]
public sealed class MissingBodyWithoutContentTypeAttribute : Attribute, IResourceFilter, IOrderedFilter
{
    public int Order => int.MinValue;

    public void OnResourceExecuting(ResourceExecutingContext context)
    {
        ArgumentNullException.ThrowIfNull(context);
        var httpContext = context.HttpContext;
        var request = httpContext.Request;
        if (!string.IsNullOrEmpty(request.ContentType))
        {
            return;
        }

        var canHaveBody = httpContext.Features.Get<IHttpRequestBodyDetectionFeature>()?.CanHaveBody ?? true;
        if (!canHaveBody || request.ContentLength == 0)
        {
            var timeProvider = httpContext.RequestServices.GetRequiredService<TimeProvider>();
            context.Result = new ObjectResult(
                ErrorResponses.SpringError(httpContext, StatusCodes.Status400BadRequest, timeProvider))
            {
                StatusCode = StatusCodes.Status400BadRequest,
            };
        }
    }

    public void OnResourceExecuted(ResourceExecutedContext context)
    {
    }
}
