using System.Text.Json;
using Payments.Models;
using Platform.Shared.Http;

namespace Payments.Services;

public sealed class RemittanceStatementClient(IConfiguration configuration, SettlementService settlements)
{
    public async Task<int> Pull(string dealerId)
    {
        var response = await SafeHttp.Fetch(configuration["Payments:Processor:RemittanceUrl"]!,
            configuration.GetSection("Payments:Processor:RemittanceAllowedHosts").Get<string[]>() ?? Array.Empty<string>());
        if (!response.IsSuccess)
        {
            throw new HttpRequestException("Remittance statement was not available.");
        }
        var rows = JsonSerializer.Deserialize<List<RemittanceRow>>(response.Body,
            new JsonSerializerOptions(JsonSerializerDefaults.Web)) ?? [];
        return await settlements.Import(dealerId, new SettlementBatch
        {
            Items = rows.Select(row => new SettlementImportItem
            {
                Reference = row.Reference,
                AmountCents = row.AmountCents
            }).ToList()
        });
    }
}
