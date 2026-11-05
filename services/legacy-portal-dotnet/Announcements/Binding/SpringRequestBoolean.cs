using Microsoft.Extensions.Primitives;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Announcements.Binding;

/// <summary>
/// Binds <c>@RequestParam(defaultValue = "...") boolean</c> the way Spring MVC 5.3 does. A missing or empty
/// parameter takes the default. Otherwise <c>StringToBooleanConverter</c> (trim, lower-case, true/on/yes/1,
/// false/off/no/0) is tried on the (first) value; when it fails or yields null, <c>TypeConverterDelegate</c> falls
/// back to <c>CustomBooleanEditor(allowEmpty=false)</c> on the comma-joined values, whose
/// <c>IllegalArgumentException("Invalid boolean value [raw]")</c> -> 400 <c>{"error","message"}</c>.
/// </summary>
public static class SpringRequestBoolean
{
    private static readonly string[] TrueValues = ["true", "on", "yes", "1"];
    private static readonly string[] FalseValues = ["false", "off", "no", "0"];

    public static bool Parse(StringValues values, bool defaultValue)
    {
        if (values.Count == 0)
        {
            return defaultValue;
        }

        var first = values[0] ?? string.Empty;
        if (values.Count == 1 && first.Length == 0)
        {
            return defaultValue;
        }

        return Convert(first) ?? Edit(values.Count == 1 ? first : string.Join(',', values.ToArray()));
    }

    private static bool? Convert(string source)
    {
        var value = JavaText.Trim(source).ToLowerInvariant();
        if (value.Length == 0)
        {
            return null;
        }

        if (TrueValues.Contains(value, StringComparer.Ordinal))
        {
            return true;
        }

        if (FalseValues.Contains(value, StringComparer.Ordinal))
        {
            return false;
        }

        return null;
    }

    private static bool Edit(string text)
    {
        var input = JavaText.Trim(text);
        if (JavaText.EqualsIgnoreCase("true", input) || JavaText.EqualsIgnoreCase("on", input)
            || JavaText.EqualsIgnoreCase("yes", input) || input == "1")
        {
            return true;
        }

        if (JavaText.EqualsIgnoreCase("false", input) || JavaText.EqualsIgnoreCase("off", input)
            || JavaText.EqualsIgnoreCase("no", input) || input == "0")
        {
            return false;
        }

        throw new PortalValidationException($"Invalid boolean value [{text}]");
    }
}
