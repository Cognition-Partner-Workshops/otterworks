using Identity.Models;
using Microsoft.EntityFrameworkCore;

namespace Identity.Repositories;

public sealed class IdentityContext(DbContextOptions<IdentityContext> options) : DbContext(options)
{
    public DbSet<Account> Accounts => Set<Account>();
    public DbSet<RegisteredDevice> Devices => Set<RegisteredDevice>();
    public DbSet<PasswordReset> PasswordResets => Set<PasswordReset>();
}
