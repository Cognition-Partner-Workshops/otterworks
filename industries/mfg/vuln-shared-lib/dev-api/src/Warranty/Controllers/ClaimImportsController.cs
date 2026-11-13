using FluentValidation;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Warranty.Models;
using Warranty.Services;

namespace Warranty.Controllers;

[Authorize]
[ApiController]
[Route("api/warranty/claims/import")]
public sealed class ClaimImportsController(ClaimService service, IValidator<ClaimImportBatch> validator) : ControllerBase
{
    [HttpPost]
    public async Task<IActionResult> Import()
    {
        using var reader = new StreamReader(Request.Body);
        var body = await reader.ReadToEndAsync();
        try
        {
            var document = JToken.Parse(body);
            if (document is JContainer container &&
                container.DescendantsAndSelf().OfType<JProperty>().Any(property => property.Name == "$type"))
            {
                return BadRequest("Type metadata is not allowed.");
            }
            var batch = document.ToObject<ClaimImportBatch>(JsonSerializer.Create(
                new JsonSerializerSettings { TypeNameHandling = TypeNameHandling.None }));
            if (batch is null || batch.Items is null)
            {
                return BadRequest("A batch is required.");
            }
            var validation = await validator.ValidateAsync(batch);
            if (!validation.IsValid)
            {
                return BadRequest(validation.Errors.Select(error => error.ErrorMessage));
            }
            return Ok(new { imported = await service.Import(User.FindFirst("dealer")!.Value, batch) });
        }
        catch (Exception exception) when (exception is JsonException or InvalidDataException)
        {
            return BadRequest("The claim batch could not be read.");
        }
    }
}
