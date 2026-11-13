using Dealer.Models;
using Dealer.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Platform.Shared.Storage;

namespace Dealer.Controllers;

[Authorize]
[ApiController]
[Route("api/dealer")]
public sealed class DealerOperationsController(
    IConfiguration configuration,
    IHttpClientFactory clients,
    ExportLinkSigner signer,
    PriceBulletinService bulletins,
    TimeProvider clock) : ControllerBase
{
    private string ExportRoot => configuration["Dealer:ExportRoot"] ?? "data/exports";

    [HttpPost("bulletins/refresh")]
    public async Task<IActionResult> Refresh()
    {
        try
        {
            return Ok(new { stored = await bulletins.Refresh() });
        }
        catch (Exception e) when (e is HttpRequestException or InvalidDataException or Newtonsoft.Json.JsonException)
        {
            return Problem("Price bulletin could not be loaded.", statusCode: 502);
        }
    }

    [HttpPost("exports/links")]
    public IActionResult CreateLink(ExportRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.FileName))
            return BadRequest();
        var expires = clock.GetUtcNow().AddMinutes(15).ToUnixTimeSeconds();
        return Ok(new { name = request.FileName, expires, signature = signer.Sign(request.FileName, expires) });
    }

    [HttpGet("exports/download")]
    public IActionResult Download(string name, long expires, string signature)
    {
        if (!signer.Verify(name, expires, signature))
            return Unauthorized();
        try
        {
            return File(FileStore.Open(ExportRoot, name), "text/csv", Path.GetFileName(name));
        }
        catch (FileNotFoundException) { return NotFound(); }
        catch (UnauthorizedAccessException) { return BadRequest(); }
    }

    [HttpGet("exports/files")]
    public IActionResult FileByName(string name)
    {
        if (string.IsNullOrWhiteSpace(name) || name != Path.GetFileName(name) ||
            name.Contains('/') || name.Contains('\\') || name is "." or "..")
            return BadRequest();
        try
        {
            if (new FileInfo(Path.Combine(ExportRoot, name)).LinkTarget is not null)
                return BadRequest();
            return File(System.IO.File.OpenRead(Path.Combine(ExportRoot, name)), "text/csv", Path.GetFileName(name));
        }
        catch (FileNotFoundException) { return NotFound(); }
    }

    [HttpGet("images/proxy")]
    public async Task<IActionResult> Image(string url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var imageUri) ||
            imageUri.Scheme != Uri.UriSchemeHttps || imageUri.Host != "images.dealer.example" ||
            !imageUri.IsDefaultPort || imageUri.UserInfo.Length != 0)
            return BadRequest();
        try
        {
            using var response = await clients.CreateClient("images").GetAsync(imageUri);
            if (!response.IsSuccessStatusCode)
                return StatusCode(502);
            return File(await response.Content.ReadAsByteArrayAsync(),
                response.Content.Headers.ContentType?.MediaType ?? "application/octet-stream");
        }
        catch (HttpRequestException) { return StatusCode(502); }
    }
}
