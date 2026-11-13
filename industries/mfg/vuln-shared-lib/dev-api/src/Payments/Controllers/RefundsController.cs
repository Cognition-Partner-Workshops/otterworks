using FluentValidation;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Payments.Models;
using Payments.Repositories;
using Payments.Services;

namespace Payments.Controllers;

[ApiController]
[Authorize(Policy = "payments")]
[Route("api/payments/refunds")]
public sealed class RefundsController(PaymentRepository repository, SettlementService settlements) : ControllerBase
{
    [Authorize(Policy = "payments")]
    [HttpGet]
    public async Task<IActionResult> List()
    {
        return Ok(await repository.Refunds(User.FindFirst("dealer")!.Value));
    }

    [HttpGet("{id:int}")]
    public async Task<IActionResult> Detail(int id)
    {
        var refund = await repository.FindRefund(User.FindFirst("dealer")!.Value, id);
        return refund is null ? NotFound() : Ok(refund);
    }

    [Authorize(Policy = "payments")]
    [HttpPost]
    public async Task<IActionResult> Create(RefundRequest request, IValidator<RefundRequest> validator)
    {
        var validation = await validator.ValidateAsync(request);
        if (!validation.IsValid)
        {
            return BadRequest(validation.Errors.Select(x => x.ErrorMessage));
        }
        try
        {
            var refund = await settlements.Refund(User.FindFirst("dealer")!.Value, request);
            return refund is null ? NotFound() : Created($"/api/payments/refunds/{refund.Id}", refund);
        }
        catch (InvalidDataException exception)
        {
            return BadRequest(exception.Message);
        }
    }
}
