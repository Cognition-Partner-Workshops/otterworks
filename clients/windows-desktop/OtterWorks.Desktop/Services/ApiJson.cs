using System;
using System.Buffers;
using System.Globalization;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace OtterWorks.Desktop.Services
{
    /// <summary>
    /// System.Text.Json settings shared by the API client, session store and settings
    /// loader. Member names come from each model's <c>[JsonPropertyName]</c>, so camelCase
    /// auth and snake_case document/file payloads use the same options. The remaining
    /// switches keep the parsing as lenient as the Json.NET defaults the client shipped with.
    /// </summary>
    internal static class ApiJson
    {
        public static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            NumberHandling = JsonNumberHandling.AllowReadingFromString,
            ReadCommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true,

            // Bodies go to the gateway, never into HTML, so only JSON-mandatory escaping applies.
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            Converters = { new LenientStringConverter(), new HalfUpTickDateTimeOffsetConverter() },
        };

        public static readonly JsonSerializerOptions Indented = new JsonSerializerOptions(Options)
        {
            WriteIndented = true,
        };

        /// <summary>Reads JSON numbers and booleans into string members, as Json.NET did (e.g. numeric ids).</summary>
        private sealed class LenientStringConverter : JsonConverter<string>
        {
            public override string? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
            {
                switch (reader.TokenType)
                {
                    case JsonTokenType.String:
                        return reader.GetString();
                    case JsonTokenType.Number:
                        return Encoding.UTF8.GetString(reader.HasValueSequence ? reader.ValueSequence.ToArray() : reader.ValueSpan.ToArray());
                    case JsonTokenType.True:
                        return "True";
                    case JsonTokenType.False:
                        return "False";
                    default:
                        throw new JsonException($"Cannot read {reader.TokenType} as a string.");
                }
            }

            public override void Write(Utf8JsonWriter writer, string value, JsonSerializerOptions options)
            {
                writer.WriteStringValue(value);
            }
        }

        /// <summary>
        /// Rounding mode for timestamps finer than a tick (100 ns), e.g. nanosecond RFC 3339
        /// stamps: keep seven fractional digits and round half up on the eighth, discarding the
        /// rest, which is what Json.NET's ISO parser did. Offset-less stamps are local time.
        /// </summary>
        private sealed class HalfUpTickDateTimeOffsetConverter : JsonConverter<DateTimeOffset>
        {
            public override DateTimeOffset Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
            {
                string text = reader.GetString() ?? throw new JsonException("Expected a timestamp string.");
                bool roundUp = false;
                int dot = text.IndexOf('.');
                if (dot > 0)
                {
                    int end = dot + 1;
                    while (end < text.Length && char.IsDigit(text[end]))
                    {
                        end++;
                    }

                    if (end - dot - 1 > 7)
                    {
                        roundUp = text[dot + 8] >= '5';
                        text = text.Substring(0, dot + 8) + text.Substring(end);
                    }
                }

                if (!DateTimeOffset.TryParse(text, CultureInfo.InvariantCulture, DateTimeStyles.AllowWhiteSpaces, out DateTimeOffset value))
                {
                    throw new JsonException($"'{text}' is not a valid timestamp.");
                }

                return roundUp ? value.AddTicks(1) : value;
            }

            public override void Write(Utf8JsonWriter writer, DateTimeOffset value, JsonSerializerOptions options)
            {
                writer.WriteStringValue(value);
            }
        }
    }
}
