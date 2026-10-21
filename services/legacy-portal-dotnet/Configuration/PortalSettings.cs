using System.Text;

namespace OtterWorks.LegacyPortal.Configuration;

/// <summary>
/// Portal branding strings from <c>portal-settings.properties</c> (port of Java <c>PortalBrandingSettings</c>).
/// Values support <c>${key}</c> references to other keys and the <c>${base64Decoder:...}</c> lookup; any other
/// <c>${prefix:...}</c> lookup (script, dns, url, env, ...) is deliberately not implemented and stays literal.
/// </summary>
public sealed class PortalSettings
{
    public const string FileName = "portal-settings.properties";

    private const string DefaultBanner = "OtterWorks Portal";
    private const string Base64DecoderPrefix = "base64Decoder:";

    private readonly IReadOnlyDictionary<string, string> _raw;

    private PortalSettings(IReadOnlyDictionary<string, string> raw)
    {
        _raw = raw;
    }

    public string Environment => Get("portal.environment") ?? string.Empty;

    public string BannerText => Get("portal.banner") ?? DefaultBanner;

    public string SupportContact => Get("portal.support") ?? string.Empty;

    public string Classification => Get("portal.classification") ?? string.Empty;

    public static PortalSettings Load(string path)
    {
        ArgumentException.ThrowIfNullOrEmpty(path);
        return Parse(File.ReadAllText(path, Encoding.Latin1));
    }

    public static PortalSettings Parse(string content)
    {
        ArgumentNullException.ThrowIfNull(content);
        return new PortalSettings(PropertiesFormat.Parse(content));
    }

    /// <summary>Interpolated value of <paramref name="key"/>, or <c>null</c> when the key is absent.</summary>
    public string? Get(string key)
    {
        ArgumentNullException.ThrowIfNull(key);
        return _raw.TryGetValue(key, out var value) ? Interpolate(value, [key]) : null;
    }

    public string Interpolate(string template)
    {
        ArgumentNullException.ThrowIfNull(template);
        return Interpolate(template, []);
    }

    private string Interpolate(string template, HashSet<string> resolving)
    {
        var result = new StringBuilder();
        var position = 0;
        while (position < template.Length)
        {
            var start = template.IndexOf("${", position, StringComparison.Ordinal);
            var end = start < 0 ? -1 : template.IndexOf('}', start + 2);
            if (end < 0)
            {
                result.Append(template, position, template.Length - position);
                break;
            }

            result.Append(template, position, start - position);
            var variable = template[(start + 2)..end];
            result.Append(Resolve(variable, resolving) ?? template[start..(end + 1)]);
            position = end + 1;
        }

        return result.ToString();
    }

    private string? Resolve(string variable, HashSet<string> resolving)
    {
        if (variable.StartsWith(Base64DecoderPrefix, StringComparison.Ordinal))
        {
            var encoded = variable[Base64DecoderPrefix.Length..];
            try
            {
                return Encoding.Latin1.GetString(Convert.FromBase64String(encoded));
            }
            catch (FormatException ex)
            {
                throw new InvalidOperationException($"Invalid base64 in ${{{variable}}}", ex);
            }
        }

        if (!_raw.TryGetValue(variable, out var value))
        {
            return null;
        }

        if (!resolving.Add(variable))
        {
            throw new InvalidOperationException($"Infinite loop in property interpolation of ${{{variable}}}");
        }

        try
        {
            return Interpolate(value, resolving);
        }
        finally
        {
            resolving.Remove(variable);
        }
    }
}
