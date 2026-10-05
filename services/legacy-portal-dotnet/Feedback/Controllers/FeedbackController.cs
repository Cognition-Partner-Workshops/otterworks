using Microsoft.AspNetCore.Mvc;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Feedback.Models;
using OtterWorks.LegacyPortal.Feedback.Services;

namespace OtterWorks.LegacyPortal.Feedback.Controllers;

[ApiController]
[Route("api/feedback")]
public sealed class FeedbackController : ControllerBase
{
    private readonly IFeedbackService _service;
    private readonly TimeProvider _timeProvider;

    public FeedbackController(IFeedbackService service, TimeProvider timeProvider)
    {
        _service = service;
        _timeProvider = timeProvider;
    }

    [HttpPost]
    [ProducesResponseType<FeedbackResponse>(StatusCodes.Status201Created)]
    public async Task<IActionResult> Submit([FromBody] SubmitFeedbackRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        var saved = await _service.SubmitAsync(request.UserId!, request.Rating, request.Message!, cancellationToken);
        return StatusCode(StatusCodes.Status201Created, FeedbackResponse.FromEntity(saved));
    }

    /// <summary>
    /// Java: <c>@RequestParam String userId</c> — required, but an empty value is accepted, and repeated values are
    /// joined with commas. Read from the raw query because MVC binding turns "" into null.
    /// </summary>
    [HttpGet]
    [ProducesResponseType<IEnumerable<FeedbackResponse>>(StatusCodes.Status200OK)]
    public async Task<IActionResult> ListForUser(CancellationToken cancellationToken)
    {
        if (!Request.Query.TryGetValue("userId", out var values))
        {
            return BadRequest(ErrorResponses.SpringError(HttpContext, StatusCodes.Status400BadRequest, _timeProvider));
        }

        var userId = string.Join(',', values.Select(v => v ?? string.Empty));
        var entries = await _service.ListForUserAsync(userId, cancellationToken);
        return Ok(entries.Select(FeedbackResponse.FromEntity).ToList());
    }

    [HttpGet("average-rating")]
    public async Task<AverageRatingResponse> AverageRating(CancellationToken cancellationToken)
    {
        return new AverageRatingResponse(await _service.AverageRatingAsync(cancellationToken));
    }
}
