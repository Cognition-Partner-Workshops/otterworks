using System.Globalization;
using System.Text.Json;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.WebUtilities;

namespace OtterWorks.LegacyPortal.Common;

/// <summary>Body written by the Java <c>GlobalExceptionHandler</c>: <c>{"error":"Not Found","message":"..."}</c>.</summary>
public sealed record ApiError(string Error, string Message)
{
    public static ApiError For(int statusCode, string message) => new(ReasonPhrases.GetReasonPhrase(statusCode), message);
}

/// <summary>
/// Body of Spring Boot's default <c>/error</c> response (DefaultErrorAttributes):
/// <c>{"timestamp":"2026-10-01T13:00:00.123+00:00","status":400,"error":"Bad Request","path":"/api/feedback"}</c>.
/// </summary>
public sealed record SpringErrorBody(string Timestamp, int Status, string Error, string Path);

public static class ErrorResponses
{
    public static SpringErrorBody SpringError(HttpContext context, int statusCode, TimeProvider timeProvider)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(timeProvider);
        var now = timeProvider.GetUtcNow().UtcDateTime;
        var timestamp = now.ToString("yyyy-MM-dd'T'HH:mm:ss.fff", CultureInfo.InvariantCulture) + "+00:00";
        return new SpringErrorBody(timestamp, statusCode, ReasonPhrases.GetReasonPhrase(statusCode), RequestUri(context));
    }

    public static Task WriteSpringErrorAsync(HttpContext context, int statusCode)
    {
        ArgumentNullException.ThrowIfNull(context);
        var timeProvider = context.RequestServices.GetService<TimeProvider>() ?? TimeProvider.System;
        return WriteJsonAsync(context, statusCode, SpringError(context, statusCode, timeProvider));
    }

    public static Task WriteApiErrorAsync(HttpContext context, int statusCode, string message)
    {
        return WriteJsonAsync(context, statusCode, ApiError.For(statusCode, message));
    }

    /// <summary>Raw request path without the query string, as Java's <c>HttpServletRequest.getRequestURI()</c>.</summary>
    public static string RequestUri(HttpContext context)
    {
        ArgumentNullException.ThrowIfNull(context);
        var rawTarget = context.Features.Get<IHttpRequestFeature>()?.RawTarget;
        if (!string.IsNullOrEmpty(rawTarget) && rawTarget.StartsWith('/'))
        {
            var queryStart = rawTarget.IndexOf('?', StringComparison.Ordinal);
            return queryStart >= 0 ? rawTarget[..queryStart] : rawTarget;
        }

        return (context.Request.PathBase + context.Request.Path).ToUriComponent();
    }

    private static async Task WriteJsonAsync<T>(HttpContext context, int statusCode, T body)
    {
        ArgumentNullException.ThrowIfNull(context);
        var options = context.RequestServices.GetService<Microsoft.Extensions.Options.IOptions<Microsoft.AspNetCore.Mvc.JsonOptions>>()?.Value.JsonSerializerOptions
            ?? SpringJson.CreateOptions();
        context.Response.StatusCode = statusCode;
        context.Response.ContentType = "application/json";
        await JsonSerializer.SerializeAsync(context.Response.Body, body, options, context.RequestAborted);
    }
}
