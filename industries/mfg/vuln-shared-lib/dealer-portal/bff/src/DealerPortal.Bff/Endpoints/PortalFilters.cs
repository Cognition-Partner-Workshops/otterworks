using DealerPortal.Bff.Session;

namespace DealerPortal.Bff.Endpoints;

public sealed class SessionFilter : IEndpointFilter
{
    private const string ItemKey = "portal.session";

    private readonly PortalSessionService _sessions;

    public SessionFilter(PortalSessionService sessions) => _sessions = sessions;

    public ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var session = _sessions.Read(context.HttpContext.Request);
        if (session is null)
        {
            return ValueTask.FromResult<object?>(Results.Unauthorized());
        }

        context.HttpContext.Items[ItemKey] = session;
        return next(context);
    }

    public static PortalSession Current(HttpContext context) =>
        context.Items[ItemKey] as PortalSession
        ?? throw new InvalidOperationException("Endpoint is not behind the session filter.");
}
