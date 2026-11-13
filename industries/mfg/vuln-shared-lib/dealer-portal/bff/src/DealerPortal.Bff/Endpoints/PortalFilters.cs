using System.Security.Cryptography;
using System.Text;
using DealerPortal.Bff.Session;
using Microsoft.Extensions.Options;

namespace DealerPortal.Bff.Endpoints;

public sealed class PortalKeyFilter : IEndpointFilter
{
    public const string Header = "X-Portal-Key";

    private readonly byte[] _expected;

    public PortalKeyFilter(IOptions<PortalOptions> options) =>
        _expected = Encoding.UTF8.GetBytes(options.Value.ClientKey);

    public ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        if (_expected.Length > 0)
        {
            var supplied = Encoding.UTF8.GetBytes(context.HttpContext.Request.Headers[Header].ToString());
            if (!CryptographicOperations.FixedTimeEquals(_expected, supplied))
            {
                return ValueTask.FromResult<object?>(Results.Unauthorized());
            }
        }

        return next(context);
    }
}

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
