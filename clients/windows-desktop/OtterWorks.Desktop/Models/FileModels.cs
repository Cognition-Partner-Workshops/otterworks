using System;
using System.Collections.Generic;
using System.Globalization;
using Newtonsoft.Json;

namespace OtterWorks.Desktop.Models
{
    /// <summary>A file as returned by the file service. Fields are snake_case.</summary>
    public class FileItem
    {
        [JsonProperty("id")]
        public string Id { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        private long? _size;
        private long? _sizeBytes;
        private string _contentType;
        private string _mimeType;

        [JsonProperty("size")]
        public long? Size
        {
            get => _size ?? _sizeBytes;
            set => _size = value;
        }

        [JsonProperty("content_type")]
        public string ContentType
        {
            get => _contentType ?? _mimeType;
            set => _contentType = value;
        }

        [JsonIgnore]
        public string SizeText => FormatSize(Size);

        // The file service sends "size_bytes" and "mime_type"; accept both spellings.
        [JsonProperty("size_bytes")]
        private long? SizeBytes
        {
            get => null;
            set => _sizeBytes = value;
        }

        [JsonProperty("mime_type")]
        private string MimeType
        {
            get => null;
            set => _mimeType = value;
        }

        [JsonProperty("created_at")]
        public DateTimeOffset? CreatedAt { get; set; }

        internal static string FormatSize(long? bytes)
        {
            if (bytes == null || bytes < 0)
            {
                return string.Empty;
            }

            string[] units = { "B", "KB", "MB", "GB", "TB" };
            double value = bytes.Value;
            int unit = 0;
            while (value >= 1024 && unit < units.Length - 1)
            {
                value /= 1024;
                unit++;
            }

            return unit == 0
                ? $"{bytes.Value} B"
                : value.ToString(value < 10 ? "0.0" : "0", CultureInfo.InvariantCulture) + " " + units[unit];
        }
    }

    /// <summary>Paged response for GET /files.</summary>
    public class FileListResponse
    {
        [JsonProperty("files")]
        public List<FileItem> Files { get; set; } = new List<FileItem>();

        [JsonProperty("total")]
        public int Total { get; set; }

        [JsonProperty("page")]
        public int Page { get; set; }

        [JsonProperty("page_size")]
        public int PageSize { get; set; }
    }
}
