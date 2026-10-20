package example.claimshub.maps;

import java.math.BigDecimal;
import java.util.Locale;
import java.util.function.Predicate;

import org.springframework.stereotype.Component;
import org.w3c.dom.Element;
import org.w3c.dom.Node;

/**
 * BizTalk map {@code Payment_to_LedgerPost}: {@code PaymentInstruction} to the {@code usp_PostClaimPayment} WCF-SQL
 * document. The C# scripting functoids are {@link #makeVendorReference} and {@link Money#format}; the Cumulative Sum
 * functoids are the per line type {@link BigDecimal} sums and Record Count is the line count.
 */
@Component
public class PaymentToLedgerPostTransformer {

    static final String SOURCE_NS = "http://schemas.thistlecombe.example/canonical/payment";
    static final String TARGET_NS = "http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo";

    public byte[] transform(byte[] source) {
        Element instruction = FlatTargetXml.parseRoot(source, SOURCE_NS, "PaymentInstruction");
        String instructionId = FlatTargetXml.text(instruction, "InstructionId");
        String claimNumber = FlatTargetXml.text(instruction, "ClaimNumber");
        return FlatTargetXml.document("ns0", TARGET_NS, "usp_PostClaimPayment")
                .element("InstructionId", instructionId)
                .element("ClaimNumber", claimNumber)
                .element("VendorReference", makeVendorReference(instructionId, claimNumber))
                .element("PayeeName", FlatTargetXml.text(instruction, "Payee", "Name"))
                .element("ValueDate", FlatTargetXml.text(instruction, "ValueDate"))
                .element("Currency", FlatTargetXml.text(instruction, "CurrencyCd"))
                .element("IndemnityAmount", Money.format(sumLines(instruction, lineType("IND"))))
                .element("ExpenseAmount", Money.format(sumLines(instruction, lineType("EXP"))))
                .element("SalvageCredit", Money.format(sumLines(instruction, lineType("SLV")).negate()))
                .element("NetAmount", Money.format(sumLines(instruction, line -> true)))
                .element("LineCount", Integer.toString(countLines(instruction)))
                .toBytes();
    }

    /**
     * C# {@code MakeVendorReference}: claim number without hyphens plus the last six characters of the instruction id,
     * upper-cased, then {@code -} and two ISO 7064 mod 97-10 check digits over the IBAN letter mapping (A..Z = 10..35).
     */
    static String makeVendorReference(String instructionId, String claimNumber) {
        String tail = instructionId.substring(Math.max(0, instructionId.length() - 6));
        String body = (claimNumber.replace("-", "") + tail).toUpperCase(Locale.ROOT);
        StringBuilder digits = new StringBuilder();
        (body + "00").codePoints().forEach(cp -> {
            if (cp >= 'A' && cp <= 'Z') {
                digits.append(cp - 'A' + 10);
            } else {
                digits.appendCodePoint(cp);
            }
        });
        int remainder = 0;
        for (int i = 0; i < digits.length(); i++) {
            remainder = (remainder * 10 + (digits.charAt(i) - '0')) % 97;
        }
        return body + "-" + String.format(Locale.ROOT, "%02d", 98 - remainder);
    }

    private static Predicate<Element> lineType(String type) {
        return line -> type.equals(FlatTargetXml.text(line, "LineType"));
    }

    private static BigDecimal sumLines(Element instruction, Predicate<Element> filter) {
        BigDecimal sum = BigDecimal.ZERO;
        for (Node node = instruction.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (isLine(node) && filter.test((Element) node)) {
                sum = sum.add(Money.parse(FlatTargetXml.text((Element) node, "Amount")));
            }
        }
        return sum;
    }

    private static int countLines(Element instruction) {
        int count = 0;
        for (Node node = instruction.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (isLine(node)) {
                count++;
            }
        }
        return count;
    }

    private static boolean isLine(Node node) {
        return node instanceof Element element && element.getNamespaceURI() == null && "Line".equals(element.getLocalName());
    }
}
