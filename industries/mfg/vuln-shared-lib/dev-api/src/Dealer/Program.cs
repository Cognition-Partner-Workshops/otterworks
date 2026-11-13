using Platform.Shared.Crypto;
using PlatformConfiguration;
using Dealer.Auth;
using Dealer.Repositories;
using Dealer.Services;
using Microsoft.AspNetCore.Authentication;

namespace Dealer;

public partial class Program
{
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);
        builder.Services.AddControllersWithViews();
        builder.Services.AddSingleton(TimeProvider.System);
        builder.Services.AddSingleton<ISigningKeyProvider>(services => SigningConfiguration.Load(services.GetRequiredService<IConfiguration>()));
        builder.Services.AddAuthentication("identity").AddScheme<AuthenticationSchemeOptions, IdentityTokenHandler>("identity", _ => { });
        builder.Services.AddAuthorization();
        builder.Services.AddSingleton<InventoryRepository>();
        builder.Services.AddSingleton<ExportLinkSigner>();
        builder.Services.AddSingleton<PriceBulletinService>();
        builder.Services.AddHttpClient("images")
            .ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler { AllowAutoRedirect = false });
        var app = builder.Build();
        _ = app.Services.GetRequiredService<ISigningKeyProvider>();
        app.Services.GetRequiredService<InventoryRepository>().Initialize();
        app.UseAuthentication();
        app.UseAuthorization();
        app.MapControllers();
        app.Run();
    }
}
