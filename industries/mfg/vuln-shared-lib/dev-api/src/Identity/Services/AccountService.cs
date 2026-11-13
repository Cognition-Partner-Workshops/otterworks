using Identity.Models;
using Identity.Repositories;
using Microsoft.EntityFrameworkCore;
using Platform.Shared.Crypto;

namespace Identity.Services;

public sealed class AccountService(IdentityContext context, ResetTokenService resets, TimeProvider clock)
{
    public Task<Account?> Find(string email)
    {
        return context.Accounts.SingleOrDefaultAsync(x => x.Email == email);
    }

    public async Task<bool> ChangePassword(string email, string currentPassword, string newPassword)
    {
        var account = await Find(email);
        if (account is null || !PasswordHasher.Verify(currentPassword, account.PasswordHash))
        {
            return false;
        }
        account.PasswordHash = PasswordHasher.Hash(newPassword);
        await context.SaveChangesAsync();
        return true;
    }

    public async Task<bool> ConfirmReset(int id, string token, string newPassword)
    {
        var reset = await context.PasswordResets.SingleOrDefaultAsync(x => x.Id == id);
        if (reset is null || reset.ExpiresAt <= clock.GetUtcNow())
        {
            return false;
        }
        string stored;
        try
        {
            stored = resets.Read(reset.ProtectedToken);
        }
        catch (System.Security.Cryptography.CryptographicException)
        {
            return false;
        }
        if (stored != token)
        {
            return false;
        }
        var account = await Find(reset.Email);
        if (account is null)
        {
            return false;
        }
        account.PasswordHash = PasswordHasher.Hash(newPassword);
        context.PasswordResets.Remove(reset);
        await context.SaveChangesAsync();
        return true;
    }
}
