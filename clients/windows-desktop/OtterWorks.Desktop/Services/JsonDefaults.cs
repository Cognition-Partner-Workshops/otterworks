using System.Text.Encodings.Web;
using System.Text.Json;

namespace OtterWorks.Desktop.Services
{
    /// <summary>
    /// Shared System.Text.Json options. Property names come from explicit
    /// <c>[JsonPropertyName]</c> attributes on each model; the remaining settings keep the
    /// lenient reading behaviour the client had with Newtonsoft.Json (case-insensitive
    /// names, comments and trailing commas tolerated, no escaping of non-ASCII text).
    /// </summary>
    internal static class JsonDefaults
    {
        public static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            ReadCommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true,
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        };
    }
}
