using System;
using System.IO;
using System.Text;
using System.Xml;
using Microsoft.BizTalk.Component.Interop;
using Microsoft.BizTalk.Message.Interop;

namespace ThistlecombeMutual.ClaimsHub.Pipelines.Components
{
    /// <summary>
    /// Decode-stage component on the FNOL receive pipeline. Rewrites every element matched by
    /// MaskedElementXPath so only the last VisibleSuffixLength characters survive; the rest become X.
    /// The business rule: a full tax id never reaches the MessageBox, tracking or the archive port.
    /// </summary>
    [ComponentCategory(CategoryTypes.CATID_PipelineComponent)]
    [ComponentCategory(CategoryTypes.CATID_Decoder)]
    [System.Runtime.InteropServices.Guid("7a2f3d10-5b6c-4e8f-9a01-2b3c4d5e6f70")]
    public class PiiMaskingComponent : IBaseComponent, IComponent, IPersistPropertyBag, IComponentUI
    {
        public string MaskedElementXPath { get; set; } = "//*[local-name()='TaxId']";
        public int VisibleSuffixLength { get; set; } = 4;

        public string Name => "PII masking";
        public string Version => "1.0";
        public string Description => "Masks tax ids to XXX-XX-nnnn before the message is persisted.";
        public IntPtr Icon => IntPtr.Zero;

        public IBaseMessage Execute(IPipelineContext context, IBaseMessage message)
        {
            var document = new XmlDocument { PreserveWhitespace = true };
            using (var reader = new StreamReader(message.BodyPart.GetOriginalDataStream(), Encoding.UTF8))
            {
                document.Load(reader);
            }

            foreach (XmlNode node in document.SelectNodes(MaskedElementXPath))
            {
                node.InnerText = Mask(node.InnerText, VisibleSuffixLength);
            }

            var output = new MemoryStream();
            document.Save(output);
            output.Position = 0;
            message.BodyPart.Data = output;
            context.ResourceTracker.AddResource(output);
            return message;
        }

        /// <summary>Keeps the separators and the last <paramref name="visible"/> digits: 123-45-6789 becomes XXX-XX-6789.</summary>
        public static string Mask(string value, int visible)
        {
            if (string.IsNullOrEmpty(value)) return value;
            var chars = value.ToCharArray();
            int digitsSeen = 0;
            for (int i = chars.Length - 1; i >= 0; i--)
            {
                if (!char.IsLetterOrDigit(chars[i])) continue;
                digitsSeen++;
                if (digitsSeen > visible) chars[i] = 'X';
            }
            return new string(chars);
        }

        public void GetClassID(out Guid classID) => classID = new Guid("7a2f3d10-5b6c-4e8f-9a01-2b3c4d5e6f70");
        public void InitNew() { }
        public void Load(IPropertyBag propertyBag, int errorLog)
        {
            object value;
            propertyBag.Read("MaskedElementXPath", out value, 0);
            if (value != null) MaskedElementXPath = (string)value;
            propertyBag.Read("VisibleSuffixLength", out value, 0);
            if (value != null) VisibleSuffixLength = (int)value;
        }
        public void Save(IPropertyBag propertyBag, bool clearDirty, bool saveAllProperties)
        {
            object xpath = MaskedElementXPath; propertyBag.Write("MaskedElementXPath", ref xpath);
            object visible = VisibleSuffixLength; propertyBag.Write("VisibleSuffixLength", ref visible);
        }
        public System.Collections.IEnumerator Validate(object projectSystem) => null;
    }
}
