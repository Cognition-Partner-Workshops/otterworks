package example.claimshub.payment;

import org.apache.camel.dataformat.bindy.annotation.DataField;
import org.apache.camel.dataformat.bindy.annotation.FixedLengthRecord;

/** PAY record of PaymentVendor_Remittance_FF.xsd; numeric fields are right-justified and zero-padded. */
@FixedLengthRecord(length = 86, paddingChar = ' ', header = RemittanceHeader.class, footer = RemittanceTrailer.class)
public class RemittancePayment {

    @DataField(pos = 1, length = 3, align = "L")
    public String recordType;
    @DataField(pos = 4, length = 4, align = "R", paddingChar = '0')
    public String lineNo;
    @DataField(pos = 8, length = 15, align = "L")
    public String claimNumber;
    @DataField(pos = 23, length = 30, align = "L")
    public String payeeName;
    @DataField(pos = 53, length = 2, align = "L")
    public String payeeType;
    @DataField(pos = 55, length = 3, align = "L")
    public String lineType;
    @DataField(pos = 58, length = 12, align = "R", paddingChar = '0')
    public String amountCents;
    @DataField(pos = 70, length = 1, align = "L")
    public String debitCreditInd;
    @DataField(pos = 71, length = 8, align = "L")
    public String valueDate;
    @DataField(pos = 79, length = 8, align = "L")
    public String glAccount;
}
