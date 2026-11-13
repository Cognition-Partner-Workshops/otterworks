using System.ComponentModel.DataAnnotations;

namespace Identity.Models;

public sealed class Account
{
    [Key]
    public string Email { get; set; } = "";
    public string DealerId { get; set; } = "";
    public string PasswordHash { get; set; } = "";
    public string Roles { get; set; } = "dealer";
}

public sealed class RegisteredDevice
{
    public int Id { get; set; }
    public string Email { get; set; } = "";
    public string DeviceId { get; set; } = "";
    public string Fingerprint { get; set; } = "";
    public DateTimeOffset RegisteredAt { get; set; }
}

public sealed class PasswordReset
{
    public int Id { get; set; }
    public string Email { get; set; } = "";
    public byte[] ProtectedToken { get; set; } = [];
    public DateTimeOffset ExpiresAt { get; set; }
}

public sealed record SignInRequest([Required, EmailAddress] string Email, [Required] string Password);
public sealed record TokenRequest([Required] string AccessToken);
public sealed record DeviceRequest([Required] string DeviceId, [Required] string UserAgent);
public sealed record RememberRequest([Required, EmailAddress] string Email);
public sealed record ResetRequest([Required, EmailAddress] string Email);
public sealed record AccessTokenResponse(string AccessToken, string TokenType, int ExpiresIn, string DealerId);
