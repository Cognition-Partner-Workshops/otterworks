using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc.Formatters;

namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// Reads request bodies the way Spring's Jackson converter does: any declared charset Jackson can decode
/// (UTF-8, UTF-16, ISO-8859-1) and only the first JSON value, ignoring trailing content
/// (Jackson's FAIL_ON_TRAILING_TOKENS is off by default).
/// </summary>
public sealed class SpringJsonInputFormatter : TextInputFormatter, IInputFormatterExceptionPolicy
{
    private static readonly byte[] Utf8Bom = [0xEF, 0xBB, 0xBF];

    public SpringJsonInputFormatter(JsonSerializerOptions serializerOptions)
    {
        SerializerOptions = serializerOptions;
        SupportedEncodings.Add(UTF8EncodingWithoutBOM);
        SupportedEncodings.Add(UTF16EncodingLittleEndian);
        SupportedEncodings.Add(Encoding.Latin1);
        SupportedMediaTypes.Add("application/json");
        SupportedMediaTypes.Add("text/json");
        SupportedMediaTypes.Add("application/*+json");
    }

    public JsonSerializerOptions SerializerOptions { get; }

    public InputFormatterExceptionPolicy ExceptionPolicy => InputFormatterExceptionPolicy.MalformedInputExceptions;

    public override async Task<InputFormatterResult> ReadRequestBodyAsync(InputFormatterContext context, Encoding encoding)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(encoding);

        using var buffer = new MemoryStream();
        await context.HttpContext.Request.Body.CopyToAsync(buffer, context.HttpContext.RequestAborted);
        var bytes = buffer.ToArray();
        if (encoding.CodePage != Encoding.UTF8.CodePage)
        {
            bytes = Encoding.Convert(encoding, Encoding.UTF8, bytes);
        }

        object? model;
        try
        {
            model = DeserializeFirstValue(bytes, context.ModelType, SerializerOptions);
        }
        catch (JsonException ex)
        {
            context.ModelState.TryAddModelError(context.ModelName, ex.Message);
            return InputFormatterResult.Failure();
        }

        if (model is null && !context.TreatEmptyInputAsDefaultValue)
        {
            return InputFormatterResult.NoValue();
        }

        return InputFormatterResult.Success(model);
    }

    public static object? DeserializeFirstValue(ReadOnlySpan<byte> utf8, Type type, JsonSerializerOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);
        if (utf8.StartsWith(Utf8Bom))
        {
            utf8 = utf8[Utf8Bom.Length..];
        }

        var reader = new Utf8JsonReader(utf8, new JsonReaderOptions
        {
            AllowTrailingCommas = options.AllowTrailingCommas,
            CommentHandling = options.ReadCommentHandling,
            MaxDepth = options.MaxDepth,
            AllowMultipleValues = true,
        });
        return JsonSerializer.Deserialize(ref reader, type, options);
    }
}
