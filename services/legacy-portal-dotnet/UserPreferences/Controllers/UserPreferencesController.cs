using Microsoft.AspNetCore.Mvc;
using OtterWorks.LegacyPortal.UserPreferences.Models;
using OtterWorks.LegacyPortal.UserPreferences.Services;

namespace OtterWorks.LegacyPortal.UserPreferences.Controllers;

[ApiController]
[Route("api/preferences")]
[Produces("application/json")]
public sealed class UserPreferencesController : ControllerBase
{
    private readonly IUserPreferenceService _service;

    public UserPreferencesController(IUserPreferenceService service)
    {
        _service = service;
    }

    [HttpGet("{userId}")]
    public async Task<PreferenceResponse> Get(string userId, CancellationToken cancellationToken)
    {
        return PreferenceResponse.FromEntity(await _service.GetOrDefaultAsync(userId, cancellationToken));
    }

    [HttpPut("{userId}")]
    [Consumes("application/json")]
    public async Task<PreferenceResponse> Update(string userId, [FromBody] UpdatePreferenceRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        var saved = await _service.SaveAsync(userId, request.Theme!, request.Locale!, request.EmailNotifications, cancellationToken);
        return PreferenceResponse.FromEntity(saved);
    }
}
