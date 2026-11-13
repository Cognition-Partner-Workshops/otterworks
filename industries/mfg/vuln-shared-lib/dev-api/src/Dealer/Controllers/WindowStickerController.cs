using Dealer.Models;
using Dealer.Repositories;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Dealer.Controllers;

[Authorize]
public sealed class WindowStickerController(InventoryRepository inventory) : Controller
{
    [HttpGet("/dealer/inventory/{vin}/sticker")]
    public async Task<IActionResult> Index(string vin, string note = "")
    {
        var vehicle = await inventory.Find(User.FindFirst("dealer")!.Value, vin);
        return vehicle is null ? NotFound() : View(new StickerModel(vehicle, note));
    }
}
