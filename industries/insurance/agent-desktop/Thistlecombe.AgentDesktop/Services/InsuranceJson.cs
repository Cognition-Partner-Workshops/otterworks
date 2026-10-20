using System.Text.Json;
using System.Text.Json.Serialization;

namespace Thistlecombe.AgentDesktop.Services
{
    public static class InsuranceJson
    {
        public static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            NumberHandling = JsonNumberHandling.AllowReadingFromString,
        };
    }
}
