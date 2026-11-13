using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Warranty.Repositories;
using Warranty.Services;

namespace Warranty.Controllers;

[Authorize]
[ApiController]
[Route("api/warranty/claims/{id:int}/attachments")]
public sealed class AttachmentsController(ClaimRepository claims, AttachmentService attachments) : ControllerBase
{
    [HttpGet]
    public async Task<IActionResult> List(int id)
    {
        if (await claims.Find(User.FindFirst("dealer")!.Value, id) is null)
        {
            return NotFound();
        }
        return Ok(attachments.List(id));
    }

    [HttpGet("preview")]
    public async Task<IActionResult> Preview(int id, string name)
    {
        if (await claims.Find(User.FindFirst("dealer")!.Value, id) is null)
        {
            return NotFound();
        }
        try
        {
            return File(attachments.Preview(id, name), "application/octet-stream");
        }
        catch (FileNotFoundException)
        {
            return NotFound();
        }
    }

    [HttpGet("download")]
    public async Task<IActionResult> Download(int id, string name)
    {
        if (await claims.Find(User.FindFirst("dealer")!.Value, id) is null)
        {
            return NotFound();
        }
        if (string.IsNullOrWhiteSpace(name) || name is "." or ".." ||
            name.IndexOfAny(['/', '\\', '\0']) >= 0 || Path.GetFileName(name) != name || Path.IsPathRooted(name))
        {
            return BadRequest("A plain file name is required.");
        }
        var attachmentRoot = Path.GetFullPath(attachments.Root(id)) + Path.DirectorySeparatorChar;
        var path = Path.GetFullPath(Path.Combine(attachmentRoot, name));
        if (!path.StartsWith(attachmentRoot, StringComparison.Ordinal))
        {
            return BadRequest("A plain file name is required.");
        }
        try
        {
            return File(System.IO.File.OpenRead(path),
                "application/octet-stream", Path.GetFileName(name));
        }
        catch (FileNotFoundException)
        {
            return NotFound();
        }
        catch (DirectoryNotFoundException)
        {
            return NotFound();
        }
    }
}
