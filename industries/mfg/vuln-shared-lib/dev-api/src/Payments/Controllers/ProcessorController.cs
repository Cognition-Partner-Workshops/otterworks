using FluentValidation;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Payments.Models;
using Payments.Repositories;
using Payments.Services;

namespace Payments.Controllers;

[ApiController]
[Route("api/payments")]
public sealed class ProcessorController(
    IConfiguration configuration,
    PaymentRepository repository,
    WebhookService webhooks,
    RemittanceStatementClient remittance) : ControllerBase
{
    [Authorize(Policy = "payments")]
    [HttpPost("processor/callback")]
    public async Task<IActionResult> Callback(ProcessorCallbackRequest request, IValidator<ProcessorCallbackRequest> validator)
    {
        if (Request.Headers["X-Processor-Secret"] != configuration["Payments:Processor:ApiSecret"])
        {
            return Unauthorized();
        }
        if (!(await validator.ValidateAsync(request)).IsValid)
        {
            return BadRequest();
        }
        var dealerId = User.FindFirst("dealer")!.Value;
        var settlement = await repository.Find(dealerId, request.SettlementId);
        if (settlement is null)
        {
            return NotFound();
        }
        settlement.Status = request.Status;
        await repository.Save();
        await webhooks.Record(dealerId, "settlement." + request.Status, settlement.Id);
        return NoContent();
    }

    [Authorize(Policy = "payments")]
    [HttpPost("remittance/pull")]
    public async Task<IActionResult> Pull()
    {
        try
        {
            return Ok(new { imported = await remittance.Pull(User.FindFirst("dealer")!.Value) });
        }
        catch (Exception exception) when (exception is HttpRequestException or InvalidDataException or System.Text.Json.JsonException)
        {
            return Problem("Remittance statement could not be loaded.", statusCode: 502);
        }
    }
}
