using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace OtterWorks.LegacyPortal.Common;

public sealed record ActuatorStatus(string Status);

public sealed record ActuatorHealth(string Status, IReadOnlyList<string> Groups);

/// <summary>
/// Spring Boot Actuator endpoints exposed by the Java service (<c>health,info</c> with probes enabled).
/// Readiness and the aggregate health include the database check; liveness reflects the process only.
/// </summary>
[ApiController]
[Route("actuator")]
[Produces("application/json")]
public sealed class ActuatorController : ControllerBase
{
    public const string ReadinessTag = "ready";

    private static readonly string[] Groups = ["liveness", "readiness"];

    private readonly HealthCheckService _healthChecks;

    public ActuatorController(HealthCheckService healthChecks)
    {
        _healthChecks = healthChecks;
    }

    [HttpGet("health")]
    public async Task<IActionResult> Health(CancellationToken cancellationToken)
    {
        var up = await IsUpAsync(_ => true, cancellationToken);
        return Respond(up, new ActuatorHealth(up ? "UP" : "DOWN", Groups));
    }

    [HttpGet("health/liveness")]
    public IActionResult Liveness() => Respond(true, new ActuatorStatus("UP"));

    [HttpGet("health/readiness")]
    public async Task<IActionResult> Readiness(CancellationToken cancellationToken)
    {
        var up = await IsUpAsync(check => check.Tags.Contains(ReadinessTag), cancellationToken);
        return Respond(up, new ActuatorStatus(up ? "UP" : "DOWN"));
    }

    [HttpGet("info")]
    public IActionResult Info() => Ok(new Dictionary<string, object>());

    private async Task<bool> IsUpAsync(Func<HealthCheckRegistration, bool> predicate, CancellationToken cancellationToken)
    {
        var report = await _healthChecks.CheckHealthAsync(predicate, cancellationToken);
        return report.Status != HealthStatus.Unhealthy;
    }

    private ObjectResult Respond<T>(bool up, T body) =>
        StatusCode(up ? StatusCodes.Status200OK : StatusCodes.Status503ServiceUnavailable, body);
}
