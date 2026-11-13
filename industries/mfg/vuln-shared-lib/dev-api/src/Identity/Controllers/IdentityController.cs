using Identity.Models;
using Identity.Repositories;
using Identity.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Platform.Shared.Crypto;

namespace Identity.Controllers;

[ApiController]
[Route("api/identity")]
public sealed class IdentityController(
    IdentityContext database,
    AccessTokenService tokens,
    RememberMeService remember,
    ResetTokenService resets,
    TimeProvider clock,
    IConfiguration configuration) : ControllerBase
{
    [HttpPost("signin")]
    public async Task<IActionResult> SignIn(SignInRequest request)
    {
        var account = await database.Accounts.SingleOrDefaultAsync(x => x.Email == request.Email);
        if (account is null || !PasswordHasher.Verify(request.Password, account.PasswordHash))
            return Unauthorized();
        return Ok(tokens.Create(account));
    }

    [HttpPost("introspect")]
    public IActionResult Introspect(TokenRequest request)
    {
        if (Request.Headers["X-Client-Secret"] != configuration["Identity:ClientSecret"])
            return Unauthorized();
        var identity = tokens.Verify(request.AccessToken);
        return identity is null ? Ok(new { active = false }) :
            Ok(new { active = true, sub = identity.Email, dealer = identity.DealerId, roles = identity.Roles });
    }

    [HttpPost("devices")]
    public async Task<IActionResult> RegisterDevice(DeviceRequest request)
    {
        var identity = CurrentIdentity();
        if (identity is null)
            return Unauthorized();
        var fingerprint = DeviceFingerprint.Compute(request.UserAgent, request.DeviceId);
        var device = new RegisteredDevice
        {
            Email = identity.Email,
            DeviceId = request.DeviceId,
            Fingerprint = fingerprint,
            RegisteredAt = clock.GetUtcNow()
        };
        database.Devices.Add(device);
        await database.SaveChangesAsync();
        return Created($"/api/identity/devices/{device.Id}", device);
    }

    [HttpPost("remember-me")]
    public IActionResult RememberMe(RememberRequest request)
    {
        var identity = CurrentIdentity();
        if (identity is null || identity.Email != request.Email)
            return Unauthorized();
        Response.Cookies.Append("remember_me", remember.Create(request.Email),
            new CookieOptions { HttpOnly = true, Secure = true, SameSite = SameSiteMode.Lax });
        return NoContent();
    }

    [HttpGet("signout")]
    public IActionResult SignOut([FromQuery] string returnUrl = "/")
    {
        Response.Cookies.Delete("remember_me");
        return Redirect(returnUrl);
    }

    [HttpPost("password-reset")]
    public async Task<IActionResult> PasswordReset(ResetRequest request)
    {
        if (await database.Accounts.AnyAsync(x => x.Email == request.Email))
        {
            database.PasswordResets.Add(new PasswordReset
            {
                Email = request.Email,
                ProtectedToken = resets.Create(request.Email),
                ExpiresAt = clock.GetUtcNow().AddMinutes(30)
            });
            await database.SaveChangesAsync();
        }
        return Accepted();
    }

    private TokenIdentity? CurrentIdentity()
    {
        var header = Request.Headers.Authorization.ToString();
        return header.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
            ? tokens.Verify(header[7..]) : null;
    }
}
