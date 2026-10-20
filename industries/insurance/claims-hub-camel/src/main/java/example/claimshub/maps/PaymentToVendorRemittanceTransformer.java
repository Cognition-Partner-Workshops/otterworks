package example.claimshub.maps;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.SAXException;

/**
 * Payment_to_VendorRemittance: one PAY record per payment line, amounts in absolute cents with a D or C
 * indicator (negative lines are credits), and a trailer with the line count, the debit and credit totals and
 * a hash that is their sum modulo ten billion. Amounts are BigDecimal; the Round functoid is .NET
 * Math.Round, so cents round HALF_EVEN. Each trailer total is the sum of the rounded line cents, which is
 * what the send pipeline's TrailerTotalsComponent recomputes; the compiled map rounds the summed amounts
 * instead, which only differs for sub-cent amounts. Output is serialised the way the map's xsl:output
 * writes it: no XML declaration, no indentation, no trailing newline. Characters XML 1.0 does not allow
 * are rejected, as Saxon's serialiser rejects them.
 */
public final class PaymentToVendorRemittanceTransformer {

    static final String SOURCE_NS = "http://schemas.thistlecombe.example/canonical/payment";
    static final String TARGET_NS = "http://schemas.thistlecombe.example/vendor/remittance";
    static final String SENDER_ID = "THISTLECMB";
    static final int PAYEE_NAME_LENGTH = 30;
    static final RoundingMode CENTS_ROUNDING = RoundingMode.HALF_EVEN;
    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
    private static final BigDecimal HASH_MODULUS = BigDecimal.valueOf(10_000_000_000L);

    public byte[] transform(byte[] source) {
        Element instruction = parse(source).getDocumentElement();
        if (!SOURCE_NS.equals(instruction.getNamespaceURI()) || !"PaymentInstruction".equals(instruction.getLocalName())) {
            throw new IllegalArgumentException("not a PaymentInstruction in " + SOURCE_NS + ": {" + instruction.getNamespaceURI() + "}" + instruction.getLocalName());
        }
        Element payee = child(instruction, "Payee");
        String claimNumber = text(instruction, "ClaimNumber");
        String payeeName = firstCodePoints(text(payee, "Name"), PAYEE_NAME_LENGTH);
        String payeeType = text(payee, "PayeeType");
        String valueDate = text(instruction, "ValueDate").replace("-", "");

        StringBuilder out = new StringBuilder(1024);
        out.append("<ns0:Remittance xmlns:ns0=\"").append(TARGET_NS).append("\">");
        out.append("<Header>");
        field(out, "RecordType", "HDR");
        field(out, "SenderId", SENDER_ID);
        field(out, "VendorCode", text(instruction, "VendorCode"));
        field(out, "FileDate", valueDate);
        field(out, "InstructionId", text(instruction, "InstructionId"));
        field(out, "Currency", text(instruction, "CurrencyCd"));
        out.append("</Header>");

        BigDecimal debitCents = BigDecimal.ZERO;
        BigDecimal creditCents = BigDecimal.ZERO;
        List<Element> lines = children(instruction, "Line");
        for (Element line : lines) {
            BigDecimal amount = amount(line);
            boolean credit = amount.signum() < 0;
            BigDecimal lineCents = cents(amount.abs());
            if (credit) {
                creditCents = creditCents.add(lineCents);
            } else {
                debitCents = debitCents.add(lineCents);
            }
            out.append("<Payment>");
            field(out, "RecordType", "PAY");
            field(out, "LineNo", text(line, "LineNo"));
            field(out, "ClaimNumber", claimNumber);
            field(out, "PayeeName", payeeName);
            field(out, "PayeeType", payeeType);
            field(out, "LineType", text(line, "LineType"));
            field(out, "AmountCents", lineCents.toPlainString());
            field(out, "DebitCreditInd", credit ? "C" : "D");
            field(out, "ValueDate", valueDate);
            field(out, "GLAccount", text(line, "GLAccount"));
            out.append("</Payment>");
        }

        out.append("<Trailer>");
        field(out, "RecordType", "TRL");
        field(out, "PaymentCount", Integer.toString(lines.size()));
        field(out, "DebitTotalCents", debitCents.toPlainString());
        field(out, "CreditTotalCents", creditCents.toPlainString());
        field(out, "HashTotal", debitCents.add(creditCents).remainder(HASH_MODULUS).toPlainString());
        out.append("</Trailer>");
        out.append("</ns0:Remittance>");
        return out.toString().getBytes(StandardCharsets.UTF_8);
    }

    static BigDecimal cents(BigDecimal amount) {
        return amount.multiply(HUNDRED).setScale(0, CENTS_ROUNDING);
    }

    private static BigDecimal amount(Element line) {
        String raw = text(line, "Amount").strip();
        try {
            return new BigDecimal(raw);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Line " + text(line, "LineNo") + ": Amount is not a decimal: '" + raw + "'", e);
        }
    }

    private static Document parse(byte[] source) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setXIncludeAware(false);
            factory.setExpandEntityReferences(false);
            DocumentBuilder builder = factory.newDocumentBuilder();
            return builder.parse(new ByteArrayInputStream(source));
        } catch (ParserConfigurationException | SAXException | IOException e) {
            throw new IllegalArgumentException("PaymentInstruction is not well-formed XML: " + e.getMessage(), e);
        }
    }

    /** Unqualified child elements, as the BizTalk instance convention has them. */
    private static List<Element> children(Element parent, String name) {
        List<Element> result = new ArrayList<>();
        if (parent == null) {
            return result;
        }
        for (Node node = parent.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element && element.getNamespaceURI() == null && name.equals(element.getLocalName())) {
                result.add(element);
            }
        }
        return result;
    }

    private static Element child(Element parent, String name) {
        List<Element> found = children(parent, name);
        return found.isEmpty() ? null : found.get(0);
    }

    /** XPath string value of the first matching child, empty when absent. */
    private static String text(Element parent, String name) {
        Element element = child(parent, name);
        return element == null ? "" : element.getTextContent();
    }

    private static String firstCodePoints(String value, int count) {
        int end = value.offsetByCodePoints(0, Math.min(count, value.codePointCount(0, value.length())));
        return value.substring(0, end);
    }

    private static boolean isXml10Char(int c) {
        return c == 0x9 || c == 0xA || (c >= 0x20 && c <= 0xD7FF) || (c >= 0xE000 && c <= 0xFFFD) || (c >= 0x10000 && c <= 0x10FFFF);
    }

    private static void field(StringBuilder out, String name, String value) {
        if (value.isEmpty()) {
            out.append('<').append(name).append("/>");
            return;
        }
        out.append('<').append(name).append('>');
        value.codePoints().forEach(c -> {
            switch (c) {
                case '&' -> out.append("&amp;");
                case '<' -> out.append("&lt;");
                case '>' -> out.append("&gt;");
                case '\r' -> out.append("&#xD;");
                default -> {
                    if (!isXml10Char(c)) {
                        throw new IllegalArgumentException(name + " contains U+" + Integer.toHexString(c).toUpperCase()
                                + ", which XML 1.0 does not allow");
                    }
                    out.appendCodePoint(c);
                }
            }
        });
        out.append("</").append(name).append('>');
    }
}
