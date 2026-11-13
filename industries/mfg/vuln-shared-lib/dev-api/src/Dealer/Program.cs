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
        builder.Services.AddAuthentication("identity").AddScheme<AuthenticationSchemeOptions, IdentityTokenHandler>("identity", _ => { });
        builder.Services.AddAuthorization();
        builder.Services.AddSingleton<InventoryRepository>();
        builder.Services.AddSingleton<ExportLinkSigner>();
        builder.Services.AddSingleton<PriceBulletinService>();
        builder.Services.AddHttpClient("images")
            .ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler { AllowAutoRedirect = false });
        var app = builder.Build();
        app.Services.GetRequiredService<InventoryRepository>().Initialize();
        app.UseAuthentication();
        app.UseAuthorization();
        app.MapControllers();
        app.Run();
    }
}
