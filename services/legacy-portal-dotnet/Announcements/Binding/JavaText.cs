using System.Globalization;

namespace OtterWorks.LegacyPortal.Announcements.Binding;

/// <summary>Java <c>String</c>/<c>Character</c> semantics the Spring binding and Bean Validation rely on.</summary>
public static class JavaText
{
    /// <summary><c>String.trim()</c>: strips every leading/trailing char &lt;= U+0020.</summary>
    public static string Trim(string value)
    {
        ArgumentNullException.ThrowIfNull(value);
        var start = 0;
        var end = value.Length;
        while (start < end && value[start] <= ' ')
        {
            start++;
        }

        while (end > start && value[end - 1] <= ' ')
        {
            end--;
        }

        return value[start..end];
    }

    /// <summary>Hibernate Validator <c>@NotBlank</c>: non-null and non-empty after <c>String.trim()</c>.</summary>
    public static bool IsNotBlank(string? value)
    {
        return value is not null && Trim(value).Length > 0;
    }

    /// <summary><c>Character.isWhitespace(char)</c> (excludes non-breaking spaces, includes U+001C..U+001F).</summary>
    public static bool IsWhitespace(char c)
    {
        if (c is '\u00A0' or '\u2007' or '\u202F')
        {
            return false;
        }

        if (c is (>= '\t' and <= '\r') or (>= '\u001C' and <= '\u001F'))
        {
            return true;
        }

        return CharUnicodeInfo.GetUnicodeCategory(c) is UnicodeCategory.SpaceSeparator
            or UnicodeCategory.LineSeparator
            or UnicodeCategory.ParagraphSeparator;
    }

    /// <summary>Spring <c>StringUtils.hasText</c>.</summary>
    public static bool HasText(string? value)
    {
        return value is not null && value.Any(c => !IsWhitespace(c));
    }

    /// <summary>Spring <c>StringUtils.trimAllWhitespace</c>: removes whitespace anywhere in the string.</summary>
    public static string TrimAllWhitespace(string value)
    {
        ArgumentNullException.ThrowIfNull(value);
        return string.Concat(value.Where(c => !IsWhitespace(c)));
    }

    /// <summary><c>String.equalsIgnoreCase</c>: per-char upper-case, then lower-case-of-upper comparison.</summary>
    public static bool EqualsIgnoreCase(string expected, string actual)
    {
        ArgumentNullException.ThrowIfNull(expected);
        ArgumentNullException.ThrowIfNull(actual);
        if (expected.Length != actual.Length)
        {
            return false;
        }

        for (var i = 0; i < expected.Length; i++)
        {
            var a = expected[i];
            var b = actual[i];
            if (a == b)
            {
                continue;
            }

            var upperA = char.ToUpperInvariant(a);
            var upperB = char.ToUpperInvariant(b);
            if (upperA != upperB && char.ToLowerInvariant(upperA) != char.ToLowerInvariant(upperB))
            {
                return false;
            }
        }

        return true;
    }

    /// <summary><c>Character.digit(char, radix)</c>: Unicode decimal digits, ASCII and full-width Latin letters.</summary>
    public static int Digit(char c, int radix)
    {
        int value;
        if (c is >= 'a' and <= 'z')
        {
            value = c - 'a' + 10;
        }
        else if (c is >= 'A' and <= 'Z')
        {
            value = c - 'A' + 10;
        }
        else if (c is >= '\uFF41' and <= '\uFF5A')
        {
            value = c - '\uFF41' + 10;
        }
        else if (c is >= '\uFF21' and <= '\uFF3A')
        {
            value = c - '\uFF21' + 10;
        }
        else if (CharUnicodeInfo.GetUnicodeCategory(c) == UnicodeCategory.DecimalDigitNumber)
        {
            value = CharUnicodeInfo.GetDecimalDigitValue(c);
        }
        else
        {
            return -1;
        }

        return value < radix ? value : -1;
    }
}
