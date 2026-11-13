using Platform.Shared.Crypto;
using PlatformConfiguration;
using FluentValidation;
using Microsoft.AspNetCore.Authentication;
using Microsoft.EntityFrameworkCore;
using Warranty.Auth;
using Warranty.Repositories;
using Warranty.Services;
using Warranty.Validation;

namespace Warranty;

public partial class Program
{
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);
        builder.Services.AddControllers();
        builder.Services.AddSingleton(TimeProvider.System);
        builder.Services.AddSingleton<ISigningKeyProvider>(services => SigningConfiguration.Load(services.GetRequiredService<IConfiguration>()));
        builder.Services.AddAuthentication("identity")
            .AddScheme<AuthenticationSchemeOptions, IdentityTokenHandler>("identity", _ => { });
        builder.Services.AddAuthorization();
        builder.Services.AddDbContext<WarrantyContext>(options =>
            options.UseSqlite(builder.Configuration.GetConnectionString("Warranty") ?? "Data Source=data/warranty.db"));
        builder.Services.AddValidatorsFromAssemblyContaining<CreateClaimValidator>();
        builder.Services.AddScoped<ClaimRepository>();
        builder.Services.AddScoped<ClaimService>();
        builder.Services.AddSingleton<AttachmentService>();
        var app = builder.Build();
        _ = app.Services.GetRequiredService<ISigningKeyProvider>();
        Directory.CreateDirectory("data");
        using (var scope = app.Services.CreateScope())
        {
            scope.ServiceProvider.GetRequiredService<WarrantyContext>().Database.EnsureCreated();
        }
        app.UseAuthentication();
        app.UseAuthorization();
        app.MapControllers();
        app.Run();
    }
}
