using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Announcements.Binding;

/// <summary>
/// Binds a <c>@PathVariable Long</c> the way Spring MVC 5.3 does: <c>StringToNumberConverterFactory</c> /
/// <c>CustomNumberEditor</c> -> <c>NumberUtils.parseNumber</c> (all whitespace removed; <c>0x</c>/<c>#</c> hex via
/// <c>Long.decode</c>, otherwise <c>Long.valueOf</c>). The resulting <c>NumberFormatException</c> reaches
/// <c>GlobalExceptionHandler</c> as an <c>IllegalArgumentException</c> -> 400 <c>{"error","message"}</c>.
/// </summary>
public static class SpringPathLong
{
    /// <summary>
    /// Returns false when the value has no text: Spring converts it to null and raises
    /// <c>MissingPathVariableException</c> (500). Throws <see cref="PortalValidationException"/> for unparsable values.
    /// </summary>
    public static bool TryParse(string raw, out long value)
    {
        ArgumentNullException.ThrowIfNull(raw);
        value = 0;
        if (!JavaText.HasText(raw))
        {
            return false;
        }

        var trimmed = JavaText.TrimAllWhitespace(raw);
        value = IsHexNumber(trimmed) ? Decode(trimmed) : ParseLong(trimmed, 10);
        return true;
    }

    /// <summary>Java 11 <c>Long.parseLong(String, int)</c>.</summary>
    public static long ParseLong(string s, int radix)
    {
        ArgumentNullException.ThrowIfNull(s);
        var len = s.Length;
        if (len == 0)
        {
            throw ForInputString(s);
        }

        var negative = false;
        var i = 0;
        var limit = -long.MaxValue;
        var firstChar = s[0];
        if (firstChar < '0')
        {
            if (firstChar == '-')
            {
                negative = true;
                limit = long.MinValue;
            }
            else if (firstChar != '+')
            {
                throw ForInputString(s);
            }

            if (len == 1)
            {
                throw ForInputString(s);
            }

            i++;
        }

        var multmin = limit / radix;
        long result = 0;
        while (i < len)
        {
            var digit = JavaText.Digit(s[i++], radix);
            if (digit < 0 || result < multmin)
            {
                throw ForInputString(s);
            }

            result *= radix;
            if (result < limit + digit)
            {
                throw ForInputString(s);
            }

            result -= digit;
        }

        return negative ? result : -result;
    }

    /// <summary>Java 11 <c>Long.decode(String)</c> (only reached for hex input).</summary>
    public static long Decode(string nm)
    {
        ArgumentNullException.ThrowIfNull(nm);
        if (nm.Length == 0)
        {
            throw new PortalValidationException("Zero length string");
        }

        var radix = 10;
        var index = 0;
        var negative = false;
        var firstChar = nm[0];
        if (firstChar == '-')
        {
            negative = true;
            index++;
        }
        else if (firstChar == '+')
        {
            index++;
        }

        if (StartsWith(nm, "0x", index) || StartsWith(nm, "0X", index))
        {
            index += 2;
            radix = 16;
        }
        else if (StartsWith(nm, "#", index))
        {
            index++;
            radix = 16;
        }
        else if (StartsWith(nm, "0", index) && nm.Length > 1 + index)
        {
            index++;
            radix = 8;
        }

        if (StartsWith(nm, "-", index) || StartsWith(nm, "+", index))
        {
            throw new PortalValidationException("Sign character in wrong position");
        }

        var digits = nm[index..];
        try
        {
            var result = ParseLong(digits, radix);
            return negative ? -result : result;
        }
        catch (PortalValidationException)
        {
            return ParseLong(negative ? "-" + digits : digits, radix);
        }
    }

    /// <summary>Spring <c>NumberUtils.isHexNumber</c>.</summary>
    private static bool IsHexNumber(string value)
    {
        var index = value.StartsWith('-') ? 1 : 0;
        return StartsWith(value, "0x", index) || StartsWith(value, "0X", index) || StartsWith(value, "#", index);
    }

    private static bool StartsWith(string value, string prefix, int index)
    {
        return index <= value.Length && value.AsSpan(index).StartsWith(prefix, StringComparison.Ordinal);
    }

    private static PortalValidationException ForInputString(string s)
    {
        return new PortalValidationException($"For input string: \"{s}\"");
    }
}
