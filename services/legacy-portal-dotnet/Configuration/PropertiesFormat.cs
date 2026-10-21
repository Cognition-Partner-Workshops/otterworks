using System.Globalization;
using System.Text;

namespace OtterWorks.LegacyPortal.Configuration;

/// <summary>
/// Reader for the Java <c>.properties</c> format: <c>#</c>/<c>!</c> comments, <c>=</c>, <c>:</c> or whitespace
/// separators, backslash line continuations and escapes (<c>\t \n \r \f \uXXXX</c>). The first occurrence of a
/// key wins, as <c>Configuration.getString</c> does for repeated keys.
/// </summary>
public static class PropertiesFormat
{
    public static IReadOnlyDictionary<string, string> Parse(string content)
    {
        ArgumentNullException.ThrowIfNull(content);
        var values = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var line in LogicalLines(content))
        {
            var (key, value) = SplitEntry(line);
            values.TryAdd(Unescape(key), Unescape(value));
        }

        return values;
    }

    private static IEnumerable<string> LogicalLines(string content)
    {
        var pending = new StringBuilder();
        foreach (var physical in content.Split('\n'))
        {
            var line = physical.TrimEnd('\r');
            line = pending.Length > 0 ? line.TrimStart() : line.TrimStart(' ', '\t', '\f');
            if (pending.Length == 0 && (line.Length == 0 || line[0] is '#' or '!'))
            {
                continue;
            }

            if (EndsWithContinuation(line))
            {
                pending.Append(line, 0, line.Length - 1);
                continue;
            }

            pending.Append(line);
            yield return pending.ToString();
            pending.Clear();
        }

        if (pending.Length > 0)
        {
            yield return pending.ToString();
        }
    }

    private static bool EndsWithContinuation(string line)
    {
        var backslashes = 0;
        for (var i = line.Length - 1; i >= 0 && line[i] == '\\'; i--)
        {
            backslashes++;
        }

        return backslashes % 2 == 1;
    }

    private static (string Key, string Value) SplitEntry(string line)
    {
        var keyEnd = 0;
        while (keyEnd < line.Length)
        {
            var c = line[keyEnd];
            if (c == '\\')
            {
                keyEnd += 2;
                continue;
            }

            if (c is '=' or ':' or ' ' or '\t' or '\f')
            {
                break;
            }

            keyEnd++;
        }

        keyEnd = Math.Min(keyEnd, line.Length);
        var valueStart = keyEnd;
        while (valueStart < line.Length && line[valueStart] is ' ' or '\t' or '\f')
        {
            valueStart++;
        }

        if (valueStart < line.Length && line[valueStart] is '=' or ':')
        {
            valueStart++;
            while (valueStart < line.Length && line[valueStart] is ' ' or '\t' or '\f')
            {
                valueStart++;
            }
        }

        return (line[..keyEnd], line[valueStart..]);
    }

    private static string Unescape(string text)
    {
        if (!text.Contains('\\', StringComparison.Ordinal))
        {
            return text;
        }

        var result = new StringBuilder(text.Length);
        for (var i = 0; i < text.Length; i++)
        {
            var c = text[i];
            if (c != '\\' || i == text.Length - 1)
            {
                result.Append(c);
                continue;
            }

            var next = text[++i];
            switch (next)
            {
                case 't': result.Append('\t'); break;
                case 'n': result.Append('\n'); break;
                case 'r': result.Append('\r'); break;
                case 'f': result.Append('\f'); break;
                case 'u' when i + 4 < text.Length
                    && int.TryParse(text.AsSpan(i + 1, 4), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var code):
                    result.Append((char)code);
                    i += 4;
                    break;
                default: result.Append(next); break;
            }
        }

        return result.ToString();
    }
}
