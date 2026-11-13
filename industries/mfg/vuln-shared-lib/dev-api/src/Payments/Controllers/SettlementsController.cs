using FluentValidation;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Newtonsoft.Json;
using Payments.Models;
using Payments.Repositories;
using Payments.Services;

namespace Payments.Controllers;

[ApiController]
[Route("api/payments/settlements")]
public sealed class SettlementsController(PaymentRepository repository, SettlementService service) : ControllerBase
{
    [Authorize(Policy = "payments")]
    [HttpGet]
    public async Task<IActionResult> List()
    {
        return Ok(await repository.List(User.FindFirst("dealer")!.Value));
    }

    [Authorize(Policy = "payments")]
    [HttpPost]
    public async Task<IActionResult> Create(CreateSettlementRequest request, IValidator<CreateSettlementRequest> validator)
    {
        var validation = await validator.ValidateAsync(request);
        if (!validation.IsValid)
        {
            return BadRequest(validation.Errors.Select(x => x.ErrorMessage));
        }
        try
        {
            var settlement = await service.Create(User.FindFirst("dealer")!.Value, request);
            return Created($"/api/payments/settlements/{settlement.Id}", settlement);
        }
        catch (DbUpdateException)
        {
            return Conflict("Settlement reference already exists.");
        }
    }

    [Authorize(Policy = "payments")]
    [HttpPost("import")]
    public async Task<IActionResult> Import()
    {
        using var reader = new StreamReader(Request.Body);
        var body = await reader.ReadToEndAsync();
        try
        {
            var batch = JsonConvert.DeserializeObject<SettlementBatch>(body,
                new JsonSerializerSettings
                {
                    TypeNameHandling = TypeNameHandling.Auto,
                    SerializationBinder = new SettlementAdjustmentBinder()
                });
            if (batch is null || batch.Items is null)
            {
                return BadRequest("A settlement batch is required.");
            }
            return Ok(new { imported = await service.Import(User.FindFirst("dealer")!.Value, batch) });
        }
        catch (Exception exception) when (exception is JsonException or InvalidDataException or OverflowException)
        {
            return BadRequest("The settlement batch could not be read.");
        }
        catch (DbUpdateException)
        {
            return Conflict("Settlement reference already exists.");
        }
    }
}
