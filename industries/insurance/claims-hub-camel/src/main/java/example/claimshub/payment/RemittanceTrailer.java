package example.claimshub.payment;

import org.apache.camel.dataformat.bindy.annotation.DataField;
import org.apache.camel.dataformat.bindy.annotation.FixedLengthRecord;

/** TRL record of PaymentVendor_Remittance_FF.xsd. */
@FixedLengthRecord(length = 47, paddingChar = ' ')
public class RemittanceTrailer {

    @DataField(pos = 1, length = 3, align = "L")
    public String recordType;
    @DataField(pos = 4, length = 6, align = "R", paddingChar = '0')
    public String paymentCount;
    @DataField(pos = 10, length = 14, align = "R", paddingChar = '0')
    public String debitTotalCents;
    @DataField(pos = 24, length = 14, align = "R", paddingChar = '0')
    public String creditTotalCents;
    @DataField(pos = 38, length = 10, align = "R", paddingChar = '0')
    public String hashTotal;
}
