using System.Text;
using Newtonsoft.Json;
using Dealer.Models;
using Dealer.Repositories;
using Platform.Shared.Http;

namespace Dealer.Services;

public sealed class PriceBulletinService(IConfiguration configuration, InventoryRepository inventory)
{
    public async Task<int> Refresh()
    {
        var response = await SafeHttp.Fetch(configuration["Dealer:PriceBulletinUrl"]!,
            configuration.GetSection("Dealer:PriceBulletinAllowedHosts").Get<string[]>() ?? Array.Empty<string>());
        if (!response.IsSuccess)
            throw new HttpRequestException("Price bulletin was not available.");
        var rows = JsonConvert.DeserializeObject<List<BulletinRow>>(Encoding.UTF8.GetString(response.Body))
            ?? [];
        if (rows.Any(x => string.IsNullOrWhiteSpace(x.Vin) || x.PriceCents < 0))
            throw new InvalidDataException("Price bulletin contains an incomplete row.");
        return await inventory.StoreBulletin(rows);
    }
}
