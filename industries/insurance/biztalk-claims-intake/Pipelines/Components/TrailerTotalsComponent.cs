using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Microsoft.BizTalk.Component.Interop;
using Microsoft.BizTalk.Message.Interop;

namespace ThistlecombeMutual.ClaimsHub.Pipelines.Components
{
    /// <summary>
    /// Encode-stage guard on the vendor send pipeline. After the flat file assembler has written the
    /// positional file, this component reads it back, recomputes the trailer from the PAY records and
    /// suspends the message when the TRL record disagrees. The vendor rejects whole files on a
    /// trailer mismatch, so it is cheaper to fail here than to wait for their morning report.
    /// Field offsets follow PaymentVendor_Remittance_FF.xsd.
    /// </summary>
    [ComponentCategory(CategoryTypes.CATID_PipelineComponent)]
    [ComponentCategory(CategoryTypes.CATID_Encoder)]
    [System.Runtime.InteropServices.Guid("7a2f3d10-5b6c-4e8f-9a01-2b3c4d5e6f71")]
    public class TrailerTotalsComponent : IBaseComponent, IComponent, IPersistPropertyBag, IComponentUI
    {
        public bool FailOnMismatch { get; set; } = true;

        public string Name => "Trailer totals guard";
        public string Version => "1.0";
        public string Description => "Recomputes TRL count, debit, credit and hash totals from PAY records.";
        public IntPtr Icon => IntPtr.Zero;

        public IBaseMessage Execute(IPipelineContext context, IBaseMessage message)
        {
            string content;
            using (var reader = new StreamReader(message.BodyPart.GetOriginalDataStream(), Encoding.ASCII))
            {
                content = reader.ReadToEnd();
            }

            var mismatch = Check(content);
            if (mismatch != null && FailOnMismatch)
            {
                throw new InvalidOperationException("Remittance trailer disagrees with body: " + mismatch);
            }

            var output = new MemoryStream(Encoding.ASCII.GetBytes(content));
            message.BodyPart.Data = output;
            context.ResourceTracker.AddResource(output);
            return message;
        }

        /// <summary>Returns null when the trailer matches, otherwise a sentence naming the first field that does not.</summary>
        public static string Check(string file)
        {
            int count = 0;
            long debit = 0, credit = 0;
            string trailer = null;
            foreach (var raw in file.Split(new[] { "\r\n" }, StringSplitOptions.RemoveEmptyEntries))
            {
                if (raw.StartsWith("PAY"))
                {
                    count++;
                    long cents = long.Parse(raw.Substring(57, 12));
                    if (raw[69] == 'C') credit += cents; else debit += cents;
                }
                else if (raw.StartsWith("TRL"))
                {
                    trailer = raw;
                }
            }
            if (trailer == null) return "no TRL record";
            if (long.Parse(trailer.Substring(3, 6)) != count) return "PaymentCount";
            if (long.Parse(trailer.Substring(9, 14)) != debit) return "DebitTotalCents";
            if (long.Parse(trailer.Substring(23, 14)) != credit) return "CreditTotalCents";
            if (long.Parse(trailer.Substring(37, 10)) != (debit + credit) % 10000000000L) return "HashTotal";
            return null;
        }

        public void GetClassID(out Guid classID) => classID = new Guid("7a2f3d10-5b6c-4e8f-9a01-2b3c4d5e6f71");
        public void InitNew() { }
        public void Load(IPropertyBag propertyBag, int errorLog)
        {
            object value;
            propertyBag.Read("FailOnMismatch", out value, 0);
            if (value != null) FailOnMismatch = (bool)value;
        }
        public void Save(IPropertyBag propertyBag, bool clearDirty, bool saveAllProperties)
        {
            object fail = FailOnMismatch; propertyBag.Write("FailOnMismatch", ref fail);
        }
        public System.Collections.IEnumerator Validate(object projectSystem) => null;
    }
}
