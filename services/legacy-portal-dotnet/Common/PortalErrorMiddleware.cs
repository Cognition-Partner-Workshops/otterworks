namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// Port of the Java <c>GlobalExceptionHandler</c> plus Spring's fallback for unhandled exceptions.
/// </summary>
public sealed class PortalErrorMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<PortalErrorMiddleware> _logger;

    public PortalErrorMiddleware(RequestDelegate next, ILogger<PortalErrorMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        ArgumentNullException.ThrowIfNull(context);
        try
        {
            await _next(context);
        }
        catch (PortalNotFoundException ex) when (!context.Response.HasStarted)
        {
            await ErrorResponses.WriteApiErrorAsync(context, StatusCodes.Status404NotFound, ex.Message);
        }
        catch (PortalValidationException ex) when (!context.Response.HasStarted)
        {
            await ErrorResponses.WriteApiErrorAsync(context, StatusCodes.Status400BadRequest, ex.Message);
        }
#pragma warning disable CA1031 // Mirrors Spring's catch-all /error handling.
        catch (Exception ex) when (!context.Response.HasStarted)
#pragma warning restore CA1031
        {
            _logger.LogError(ex, "Unhandled exception for {Method} {Path}", context.Request.Method, context.Request.Path);
            await ErrorResponses.WriteSpringErrorAsync(context, StatusCodes.Status500InternalServerError);
        }
    }
}
