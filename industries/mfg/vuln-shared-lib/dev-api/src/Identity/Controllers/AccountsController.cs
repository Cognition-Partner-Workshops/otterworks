using System.ComponentModel.DataAnnotations;
using Identity.Services;
using Microsoft.AspNetCore.Mvc;

namespace Identity.Controllers;

[ApiController]
[Route("api/identity/account")]
public sealed class AccountsController(AccountService accounts, AccessTokenService tokens) : ControllerBase
{
    private TokenIdentity? Current()
    {
        var header = Request.Headers.Authorization.ToString();
        return header.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
            ? tokens.Verify(header[7..]) : null;
    }

    [HttpGet]
    public async Task<IActionResult> Profile()
    {
        var identity = Current();
        if (identity is null)
        {
            return Unauthorized();
        }
        var account = await accounts.Find(identity.Email);
        return account is null ? NotFound() :
            Ok(new { account.Email, account.DealerId, roles = account.Roles.Split(',') });
    }

    [HttpPost("password")]
    public async Task<IActionResult> ChangePassword(ChangePasswordRequest request)
    {
        var identity = Current();
        if (identity is null)
        {
            return Unauthorized();
        }
        var changed = await accounts.ChangePassword(identity.Email, request.CurrentPassword, request.NewPassword);
        return changed ? NoContent() : Unauthorized();
    }

    [HttpPost("reset-confirm")]
    public async Task<IActionResult> ConfirmReset(ConfirmResetRequest request)
    {
        var changed = await accounts.ConfirmReset(request.Id, request.Token, request.NewPassword);
        return changed ? NoContent() : BadRequest("Reset request could not be confirmed.");
    }
}

public sealed record ChangePasswordRequest(
    [Required] string CurrentPassword,
    [Required, MinLength(12)] string NewPassword);

public sealed record ConfirmResetRequest(
    int Id,
    [Required] string Token,
    [Required, MinLength(12)] string NewPassword);
