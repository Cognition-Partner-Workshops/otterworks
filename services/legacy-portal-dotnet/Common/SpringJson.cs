using System.Text.Encodings.Web;
using System.Text.Json;

namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// JSON settings that reproduce the wire format of the Java service (Spring Boot 2.7 / Jackson 2.13 defaults).
/// </summary>
public static class SpringJson
{
    public static void Configure(JsonSerializerOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);
        options.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
        options.PropertyNameCaseInsensitive = false;
        options.Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping;
        options.Converters.Add(new LenientInt32Converter());
        options.Converters.Add(new LenientBooleanConverter());
        options.Converters.Add(new LenientStringConverter());
        options.Converters.Add(new JavaDoubleConverter());
        options.Converters.Add(new IsoInstantConverter());
    }

    public static JsonSerializerOptions CreateOptions()
    {
        var options = new JsonSerializerOptions(JsonSerializerDefaults.Web);
        Configure(options);
        return options;
    }
}
