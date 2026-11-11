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

        [JsonProperty("size_bytes")]
        public long? Size { get; set; }

        [JsonProperty("mime_type")]
        public string ContentType { get; set; }

        [JsonProperty("created_at")]
        public DateTimeOffset? CreatedAt { get; set; }

        [JsonIgnore]
        public string SizeDisplay
        {
            get
            {
                if (Size == null)
                {
                    return string.Empty;
                }

                double size = Size.Value;
                string[] units = { "B", "KB", "MB", "GB", "TB" };
                int unit = 0;
                while (size >= 1024 && unit < units.Length - 1)
                {
                    size /= 1024;
                    unit++;
                }

                return unit == 0
                    ? string.Format(CultureInfo.CurrentCulture, "{0} {1}", Size.Value, units[unit])
                    : string.Format(CultureInfo.CurrentCulture, "{0:0.#} {1}", size, units[unit]);
            }
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
