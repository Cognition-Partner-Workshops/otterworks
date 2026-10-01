using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// Jackson-compatible <c>int</c> binding: JSON null or a missing property yields 0, whole-number floats and
/// numeric strings are coerced, and out-of-range values are rejected (400).
/// </summary>
public sealed class LenientInt32Converter : JsonConverter<int>
{
    public override bool HandleNull => true;

    public override int Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        switch (reader.TokenType)
        {
            case JsonTokenType.Null:
                return 0;
            case JsonTokenType.Number:
                if (reader.TryGetInt32(out var whole))
                {
                    return whole;
                }

                var number = reader.GetDouble();
                if (number >= int.MinValue && number <= int.MaxValue && !double.IsInfinity(number))
                {
                    if (reader.TryGetInt64(out _))
                    {
                        throw new JsonException("Numeric value out of range of int");
                    }

                    return (int)Math.Truncate(number);
                }

                throw new JsonException("Numeric value out of range of int");
            case JsonTokenType.String:
                var text = reader.GetString()!.Trim();
                if (text.Length == 0)
                {
                    return 0;
                }

                if (int.TryParse(text, NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out var parsed))
                {
                    return parsed;
                }

                throw new JsonException($"Cannot coerce String \"{text}\" to int");
            case JsonTokenType.True:
            case JsonTokenType.False:
            case JsonTokenType.StartObject:
            case JsonTokenType.StartArray:
            default:
                throw new JsonException($"Cannot deserialize value of type int from {reader.TokenType}");
        }
    }

    public override void Write(Utf8JsonWriter writer, int value, JsonSerializerOptions options)
    {
        ArgumentNullException.ThrowIfNull(writer);
        writer.WriteNumberValue(value);
    }
}

/// <summary>
/// Jackson-compatible <c>boolean</c> binding: JSON null or missing yields false, "true"/"false" strings
/// (case-insensitive) and integers (0 = false) are coerced.
/// </summary>
public sealed class LenientBooleanConverter : JsonConverter<bool>
{
    public override bool HandleNull => true;

    public override bool Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        switch (reader.TokenType)
        {
            case JsonTokenType.True:
                return true;
            case JsonTokenType.False:
            case JsonTokenType.Null:
                return false;
            case JsonTokenType.Number when reader.TryGetInt64(out var number):
                return number != 0;
            case JsonTokenType.String:
                var text = reader.GetString()!.Trim();
                if (text.Length == 0)
                {
                    return false;
                }

                if (bool.TryParse(text, out var parsed))
                {
                    return parsed;
                }

                throw new JsonException($"Cannot coerce String \"{text}\" to boolean");
            default:
                throw new JsonException($"Cannot deserialize value of type boolean from {reader.TokenType}");
        }
    }

    public override void Write(Utf8JsonWriter writer, bool value, JsonSerializerOptions options)
    {
        ArgumentNullException.ThrowIfNull(writer);
        writer.WriteBooleanValue(value);
    }
}

/// <summary>Jackson-compatible <c>String</c> binding: scalar numbers and booleans are accepted as their text.</summary>
public sealed class LenientStringConverter : JsonConverter<string>
{
    public override string? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        return reader.TokenType switch
        {
            JsonTokenType.String => reader.GetString(),
            JsonTokenType.Null => null,
            JsonTokenType.True => "true",
            JsonTokenType.False => "false",
            JsonTokenType.Number => System.Text.Encoding.UTF8.GetString(
                reader.HasValueSequence ? System.Buffers.BuffersExtensions.ToArray(reader.ValueSequence) : reader.ValueSpan),
            _ => throw new JsonException($"Cannot deserialize value of type String from {reader.TokenType}"),
        };
    }

    public override void Write(Utf8JsonWriter writer, string value, JsonSerializerOptions options)
    {
        ArgumentNullException.ThrowIfNull(writer);
        writer.WriteStringValue(value);
    }
}

/// <summary>Writes doubles the way Java's <c>Double.toString</c> does for typical values (e.g. 4.0, 3.5).</summary>
public sealed class JavaDoubleConverter : JsonConverter<double>
{
    public override double Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        return reader.TokenType switch
        {
            JsonTokenType.Number => reader.GetDouble(),
            JsonTokenType.Null => 0.0,
            JsonTokenType.String when double.TryParse(reader.GetString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var d) => d,
            _ => throw new JsonException($"Cannot deserialize value of type double from {reader.TokenType}"),
        };
    }

    public override void Write(Utf8JsonWriter writer, double value, JsonSerializerOptions options)
    {
        ArgumentNullException.ThrowIfNull(writer);
        writer.WriteRawValue(Format(value), skipInputValidation: true);
    }

    public static string Format(double value)
    {
        if (double.IsNaN(value) || double.IsInfinity(value))
        {
            return "null";
        }

        var abs = Math.Abs(value);
        if (abs != 0 && (abs < 1e-3 || abs >= 1e7))
        {
            var exponent = value.ToString("R", CultureInfo.InvariantCulture).ToUpperInvariant().Replace("E+", "E", StringComparison.Ordinal);
            return exponent.Contains('E', StringComparison.Ordinal) && !exponent.Split('E')[0].Contains('.', StringComparison.Ordinal)
                ? exponent.Replace("E", ".0E", StringComparison.Ordinal)
                : exponent;
        }

        var text = value.ToString("R", CultureInfo.InvariantCulture);
        return text.Contains('.', StringComparison.Ordinal) ? text : text + ".0";
    }
}

/// <summary>
/// Serializes UTC <see cref="DateTime"/> values like Java's <c>Instant.toString()</c> (ISO_INSTANT): fractional
/// seconds are omitted when zero and otherwise printed as 3, 6 or 9 digits.
/// </summary>
public sealed class IsoInstantConverter : JsonConverter<DateTime>
{
    public override DateTime Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        var text = reader.GetString() ?? throw new JsonException("Expected an ISO-8601 instant");
        return DateTime.Parse(text, CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal);
    }

    public override void Write(Utf8JsonWriter writer, DateTime value, JsonSerializerOptions options)
    {
        ArgumentNullException.ThrowIfNull(writer);
        writer.WriteStringValue(Format(value));
    }

    public static string Format(DateTime value)
    {
        var utc = value.Kind == DateTimeKind.Local ? value.ToUniversalTime() : value;
        var nanos = (utc.Ticks % TimeSpan.TicksPerSecond) * 100;
        var seconds = utc.ToString("yyyy-MM-dd'T'HH:mm:ss", CultureInfo.InvariantCulture);
        if (nanos == 0)
        {
            return seconds + "Z";
        }

        if (nanos % 1_000_000 == 0)
        {
            return seconds + "." + (nanos / 1_000_000).ToString("D3", CultureInfo.InvariantCulture) + "Z";
        }

        if (nanos % 1_000 == 0)
        {
            return seconds + "." + (nanos / 1_000).ToString("D6", CultureInfo.InvariantCulture) + "Z";
        }

        return seconds + "." + nanos.ToString("D9", CultureInfo.InvariantCulture) + "Z";
    }
}
