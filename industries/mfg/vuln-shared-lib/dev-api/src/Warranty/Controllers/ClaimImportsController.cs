using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Newtonsoft.Json;
using Warranty.Models;
using Warranty.Services;

namespace Warranty.Controllers;

[Authorize]
[ApiController]
[Route("api/warranty/claims/import")]
public sealed class ClaimImportsController(ClaimService service) : ControllerBase
{
    [HttpPost]
    public async Task<IActionResult> Import()
    {
        using var reader = new StreamReader(Request.Body);
        var body = await reader.ReadToEndAsync();
        try
        {
            var batch = JsonConvert.DeserializeObject<ClaimImportBatch>(body,
                new JsonSerializerSettings { TypeNameHandling = TypeNameHandling.All });
            if (batch is null || batch.Items is null)
            {
                return BadRequest("A batch is required.");
            }
            return Ok(new { imported = await service.Import(User.FindFirst("dealer")!.Value, batch) });
        }
        catch (Exception exception) when (exception is JsonException or InvalidDataException)
        {
            return BadRequest("The claim batch could not be read.");
        }
    }
}
