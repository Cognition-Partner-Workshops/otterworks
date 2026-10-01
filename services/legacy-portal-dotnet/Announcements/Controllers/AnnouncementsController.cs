using Microsoft.AspNetCore.Mvc;
using OtterWorks.LegacyPortal.Announcements.Binding;
using OtterWorks.LegacyPortal.Announcements.Models;
using OtterWorks.LegacyPortal.Announcements.Services;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Announcements.Controllers;

[ApiController]
[Route("api/announcements")]
[CaseSensitiveRoute("/api/announcements")]
[Produces("application/json")]
public sealed class AnnouncementsController : ControllerBase
{
    private readonly IAnnouncementService _service;
    private readonly TimeProvider _timeProvider;

    public AnnouncementsController(IAnnouncementService service, TimeProvider timeProvider)
    {
        _service = service;
        _timeProvider = timeProvider;
    }

    [HttpGet]
    [HttpHead]
    public async Task<IReadOnlyList<AnnouncementResponse>> List(CancellationToken cancellationToken)
    {
        var publishedOnly = SpringRequestBoolean.Parse(Request.Query["publishedOnly"], defaultValue: true);
        var announcements = publishedOnly
            ? await _service.ListPublishedAsync(cancellationToken)
            : await _service.ListAllAsync(cancellationToken);
        return announcements.Select(AnnouncementResponse.FromEntity).ToList();
    }

    [HttpGet("{id}")]
    [HttpHead("{id}")]
    public async Task<ActionResult<AnnouncementResponse>> Get(string id, CancellationToken cancellationToken)
    {
        if (!SpringPathLong.TryParse(id, out var announcementId))
        {
            return MissingPathVariable();
        }

        return AnnouncementResponse.FromEntity(await _service.GetAsync(announcementId, cancellationToken));
    }

    [HttpPost]
    [MissingBodyWithoutContentType]
    [Consumes("application/json", "application/*+json")]
    [ProducesResponseType(StatusCodes.Status201Created)]
    public async Task<ActionResult<AnnouncementResponse>> Create(
        [FromBody] CreateAnnouncementRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        var announcement = await _service.CreateAsync(request.Title!, request.Body!, request.Published, cancellationToken);
        return StatusCode(StatusCodes.Status201Created, AnnouncementResponse.FromEntity(announcement));
    }

    [HttpPost("{id}/publish")]
    public async Task<ActionResult<AnnouncementResponse>> Publish(string id, CancellationToken cancellationToken)
    {
        if (!SpringPathLong.TryParse(id, out var announcementId))
        {
            return MissingPathVariable();
        }

        return AnnouncementResponse.FromEntity(await _service.PublishAsync(announcementId, cancellationToken));
    }

    private ObjectResult MissingPathVariable()
    {
        return StatusCode(
            StatusCodes.Status500InternalServerError,
            ErrorResponses.SpringError(HttpContext, StatusCodes.Status500InternalServerError, _timeProvider));
    }
}
