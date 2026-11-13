using Dealer.Models;
using Dealer.Repositories;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Dealer.Controllers;

[Authorize]
[ApiController]
[Route("api/dealer")]
public sealed class InventoryController(InventoryRepository inventory) : ControllerBase
{
    [HttpGet("inventory")]
    public async Task<IActionResult> List(string dealerId, int page = 1, int size = 50)
    {
        if (!Owns(dealerId))
            return Forbid();
        return Ok((await inventory.Inventory(dealerId, page, size)).Select(InventoryItem.From));
    }

    [HttpGet("inventory/search")]
    public async Task<IActionResult> Search(string dealerId, string model = "")
    {
        if (!Owns(dealerId))
            return Forbid();
        return Ok((await inventory.Search(dealerId, model)).Select(InventoryItem.From));
    }

    [HttpGet("reports/aging")]
    public async Task<IActionResult> Aging(string dealerId, string sort = "DaysInStock DESC")
    {
        if (!Owns(dealerId))
            return Forbid();
        return Ok(await inventory.Aging(dealerId, sort));
    }

    private bool Owns(string dealerId) => User.FindFirst("dealer")?.Value == dealerId;
}
