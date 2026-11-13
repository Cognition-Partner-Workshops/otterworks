using Platform.Shared.Crypto;
using PlatformConfiguration;
using Identity.Repositories;
using Identity.Services;
using Microsoft.EntityFrameworkCore;

namespace Identity;

public partial class Program
{
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);
        builder.Services.AddControllers();
        builder.Services.AddSingleton(TimeProvider.System);
        builder.Services.AddSingleton<ISigningKeyProvider>(services => SigningConfiguration.Load(services.GetRequiredService<IConfiguration>()));
        builder.Services.AddDbContext<IdentityContext>(options =>
            options.UseSqlite(builder.Configuration.GetConnectionString("Identity") ?? "Data Source=data/identity.db"));
        builder.Services.AddSingleton<AccessTokenService>();
        builder.Services.AddSingleton<RememberMeService>();
        builder.Services.AddSingleton<ResetTokenService>();
        builder.Services.AddScoped<AccountService>();
        var app = builder.Build();
        _ = app.Services.GetRequiredService<ISigningKeyProvider>();
        Directory.CreateDirectory("data");
        using (var scope = app.Services.CreateScope())
            scope.ServiceProvider.GetRequiredService<IdentityContext>().Database.EnsureCreated();
        app.MapControllers();
        app.Run();
    }
}
