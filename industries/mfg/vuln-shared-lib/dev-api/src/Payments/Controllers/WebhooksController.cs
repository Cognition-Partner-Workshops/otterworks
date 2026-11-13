using FluentValidation;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Payments.Models;
using Payments.Repositories;
using Payments.Services;

namespace Payments.Controllers;

[ApiController]
[Route("api/payments/webhooks")]
public sealed class WebhooksController(WebhookService service, PaymentRepository repository) : ControllerBase
{
    [Authorize(Policy = "payments")]
    [HttpGet("events")]
    public async Task<IActionResult> Events()
    {
        return Ok(await repository.Events(User.FindFirst("dealer")!.Value));
    }

    [Authorize(Policy = "payments")]
    [HttpPost("test")]
    public async Task<IActionResult> Test(WebhookTestRequest request, IValidator<WebhookTestRequest> validator)
    {
        if (!(await validator.ValidateAsync(request)).IsValid)
        {
            return BadRequest();
        }
        try
        {
            var delivered = await service.SendSample(User.FindFirst("dealer")!.Value, request.Url);
            return delivered ? Ok(new { delivered }) : StatusCode(502);
        }
        catch (HttpRequestException)
        {
            return StatusCode(502);
        }
    }
}
