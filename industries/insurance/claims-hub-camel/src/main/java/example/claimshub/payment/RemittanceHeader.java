package example.claimshub.payment;

import org.apache.camel.dataformat.bindy.annotation.DataField;
import org.apache.camel.dataformat.bindy.annotation.FixedLengthRecord;

/** HDR record of PaymentVendor_Remittance_FF.xsd. */
@FixedLengthRecord(length = 46, paddingChar = ' ')
public class RemittanceHeader {

    @DataField(pos = 1, length = 3, align = "L")
    public String recordType;
    @DataField(pos = 4, length = 10, align = "L")
    public String senderId;
    @DataField(pos = 14, length = 6, align = "L")
    public String vendorCode;
    @DataField(pos = 20, length = 8, align = "L")
    public String fileDate;
    @DataField(pos = 28, length = 16, align = "L")
    public String instructionId;
    @DataField(pos = 44, length = 3, align = "L")
    public String currency;
}
