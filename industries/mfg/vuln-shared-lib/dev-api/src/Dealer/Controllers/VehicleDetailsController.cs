using Dealer.Models;
using Dealer.Repositories;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Dealer.Controllers;

[Authorize]
[ApiController]
[Route("api/dealer/vehicles")]
public sealed class VehicleDetailsController(InventoryRepository repository) : ControllerBase
{
    private string DealerId => User.FindFirst("dealer")!.Value;

    [HttpGet("{vin}")]
    public async Task<IActionResult> Detail(string vin)
    {
        var vehicle = await repository.Find(DealerId, vin);
        return vehicle is null ? NotFound() : Ok(vehicle);
    }

    [HttpGet]
    public async Task<IActionResult> Browse(string term = "", string sort = "Vin", int page = 1, int size = 50)
    {
        return Ok(await repository.Browse(DealerId, term, sort, page, size));
    }

    [HttpPost("selection")]
    public async Task<IActionResult> Selection(string[] vins)
    {
        return Ok(await repository.ByVins(DealerId, vins));
    }

    [HttpPut("{vin}/status")]
    public async Task<IActionResult> Status(string vin, VehicleStatusRequest request)
    {
        if (request.Status is not ("available" or "reserved" or "sold"))
        {
            return BadRequest("Status is not recognized.");
        }
        return await repository.UpdateStatus(DealerId, vin, request.Status) ? NoContent() : NotFound();
    }

    [HttpPut("{vin}/price")]
    public async Task<IActionResult> Price(string vin, VehiclePriceRequest request)
    {
        if (request.PriceCents < 0)
        {
            return BadRequest("Price must be nonnegative.");
        }
        return await repository.UpdatePrice(DealerId, vin, request.PriceCents) ? NoContent() : NotFound();
    }

    [HttpGet("{vin}/prices")]
    public async Task<IActionResult> Prices(string vin)
    {
        if (await repository.Find(DealerId, vin) is null)
        {
            return NotFound();
        }
        return Ok(await repository.PriceHistory(DealerId, vin));
    }
}

public sealed record VehicleStatusRequest(string Status);
public sealed record VehiclePriceRequest(long PriceCents);
