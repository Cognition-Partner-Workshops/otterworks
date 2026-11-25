package example.claimshub.payment;

import java.io.StringReader;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.camel.Exchange;
import org.apache.camel.dataformat.bindy.fixed.BindyFixedLengthDataFormat;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;

/**
 * Turns the Payment_to_VendorRemittance XML into the bindy records, the job the flat-file assembler did with
 * the schema annotations. Field text is taken as the map wrote it; bindy only pads it to the schema widths.
 */
public final class RemittanceRecords {

    private RemittanceRecords() {
    }

    public static List<RemittancePayment> toRecords(Exchange exchange) throws Exception {
        String xml = exchange.getMessage().getMandatoryBody(String.class);
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element root = factory.newDocumentBuilder().parse(new InputSource(new StringReader(xml))).getDocumentElement();

        RemittanceHeader header = new RemittanceHeader();
        RemittanceTrailer trailer = new RemittanceTrailer();
        List<RemittancePayment> payments = new ArrayList<>();
        for (Node n = root.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (!(n instanceof Element record)) {
                continue;
            }
            switch (record.getLocalName()) {
                case "Header" -> {
                    header.recordType = text(record, "RecordType");
                    header.senderId = text(record, "SenderId");
                    header.vendorCode = text(record, "VendorCode");
                    header.fileDate = text(record, "FileDate");
                    header.instructionId = text(record, "InstructionId");
                    header.currency = text(record, "Currency");
                }
                case "Payment" -> {
                    RemittancePayment pay = new RemittancePayment();
                    pay.recordType = text(record, "RecordType");
                    pay.lineNo = text(record, "LineNo");
                    pay.claimNumber = text(record, "ClaimNumber");
                    pay.payeeName = text(record, "PayeeName");
                    pay.payeeType = text(record, "PayeeType");
                    pay.lineType = text(record, "LineType");
                    pay.amountCents = text(record, "AmountCents");
                    pay.debitCreditInd = text(record, "DebitCreditInd");
                    pay.valueDate = text(record, "ValueDate");
                    pay.glAccount = text(record, "GLAccount");
                    payments.add(pay);
                }
                case "Trailer" -> {
                    trailer.recordType = text(record, "RecordType");
                    trailer.paymentCount = text(record, "PaymentCount");
                    trailer.debitTotalCents = text(record, "DebitTotalCents");
                    trailer.creditTotalCents = text(record, "CreditTotalCents");
                    trailer.hashTotal = text(record, "HashTotal");
                }
                default -> throw new IllegalArgumentException("unexpected remittance record " + record.getLocalName());
            }
        }
        exchange.getMessage().setHeader(BindyFixedLengthDataFormat.CAMEL_BINDY_FIXED_LENGTH_HEADER,
                Map.of(RemittanceHeader.class.getName(), header));
        exchange.getMessage().setHeader(BindyFixedLengthDataFormat.CAMEL_BINDY_FIXED_LENGTH_FOOTER,
                Map.of(RemittanceTrailer.class.getName(), trailer));
        return payments;
    }

    private static String text(Element record, String field) {
        for (Node n = record.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element e && field.equals(e.getLocalName())) {
                return e.getTextContent();
            }
        }
        return "";
    }
}
