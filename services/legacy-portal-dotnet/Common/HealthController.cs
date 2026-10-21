using Microsoft.AspNetCore.Mvc;
using OtterWorks.LegacyPortal.Configuration;

namespace OtterWorks.LegacyPortal.Common;

public sealed record HealthResponse(string Status, string Service, string Banner);

/// <summary>Port of Java <c>common/HealthController</c>: the OtterWorks <c>/health</c> convention.</summary>
[ApiController]
public sealed class HealthController : ControllerBase
{
    private readonly PortalSettings _settings;

    public HealthController(PortalSettings settings)
    {
        _settings = settings;
    }

    [HttpGet("health")]
    [Produces("application/json")]
    public HealthResponse Health() => new("UP", "legacy-portal", _settings.BannerText);
}
