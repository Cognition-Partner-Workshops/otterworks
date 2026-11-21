using Microsoft.VisualStudio.TestTools.UnitTesting;
using Newtonsoft.Json;
using OtterWorks.Desktop.Models;

namespace OtterWorks.Desktop.Tests
{
    [TestClass]
    public class FileItemTests
    {
        [DataTestMethod]
        [DataRow(null, "")]
        [DataRow(0L, "0 B")]
        [DataRow(1023L, "1023 B")]
        [DataRow(1024L, "1.0 KB")]
        [DataRow(48213L, "47 KB")]
        [DataRow(5L * 1024 * 1024, "5.0 MB")]
        public void FormatSize_RendersHumanReadableSizes(long? bytes, string expected)
        {
            Assert.AreEqual(expected, FileItem.FormatSize(bytes));
        }

        [TestMethod]
        public void Deserialise_LegacySizeAndContentTypeFields_StillMap()
        {
            var file = JsonConvert.DeserializeObject<FileItem>(
                "{\"id\":\"f1\",\"name\":\"notes.txt\",\"size\":12,\"content_type\":\"text/plain\"}");

            Assert.AreEqual(12L, file.Size);
            Assert.AreEqual("text/plain", file.ContentType);
        }
    }
}
