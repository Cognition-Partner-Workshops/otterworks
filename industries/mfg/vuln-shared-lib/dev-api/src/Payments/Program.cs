using FluentValidation;
using Microsoft.AspNetCore.Authentication;
using Microsoft.EntityFrameworkCore;
using Payments.Auth;
using Payments.Repositories;
using Payments.Services;
using Payments.Validation;

namespace Payments;

public partial class Program
{
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);
        builder.Services.AddControllers();
        builder.Services.AddSingleton(TimeProvider.System);
        builder.Services.AddAuthentication("identity")
            .AddScheme<AuthenticationSchemeOptions, IdentityTokenHandler>("identity", _ => { });
        builder.Services.AddAuthorization(options =>
            options.AddPolicy("payments", policy => policy.RequireAuthenticatedUser().RequireRole("payments")));
        builder.Services.AddDbContext<PaymentsContext>(options =>
            options.UseSqlite(builder.Configuration.GetConnectionString("Payments") ?? "Data Source=data/payments.db"));
        builder.Services.AddValidatorsFromAssemblyContaining<RefundValidator>();
        builder.Services.AddScoped<PaymentRepository>();
        builder.Services.AddScoped<SettlementService>();
        builder.Services.AddScoped<WebhookService>();
        builder.Services.AddScoped<RemittanceStatementClient>();
        builder.Services.AddSingleton<WebhookSigner>();
        builder.Services.AddHttpClient("webhooks");
        var app = builder.Build();
        Directory.CreateDirectory("data");
        using (var scope = app.Services.CreateScope())
        {
            scope.ServiceProvider.GetRequiredService<PaymentsContext>().Database.EnsureCreated();
        }
        app.UseAuthentication();
        app.UseAuthorization();
        app.MapControllers();
        app.Run();
    }
}
