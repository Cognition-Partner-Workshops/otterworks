package example.claimshub.payment;

import java.io.StringReader;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;

/** ThistlecombeMutual.ClaimsHub.Helpers.OpsMail.PaymentHeld(msgInstruction, attempts), and the same note for a refused file. */
public final class OpsMail {

    private OpsMail() {
    }

    public record Note(String subject, String body) {
    }

    public static Note paymentHeld(String instruction, int attempts) throws Exception {
        Element root = parse(instruction);
        String claim = child(root, "ClaimNumber");
        String body = "Payment instruction " + child(root, "InstructionId") + " for claim " + claim + " was not delivered to the payment vendor after "
                + attempts + " attempts.\r\nThe ledger post has been reversed. Re-release the instruction once the vendor is reachable.\r\n";
        return new Note("Payment held: " + claim, body);
    }

    /** The send pipeline's trailer check refused the remittance before it reached the vendor. */
    public static Note fileRefused(String instruction, String reason) throws Exception {
        Element root = parse(instruction);
        String claim = child(root, "ClaimNumber");
        String body = "Payment instruction " + child(root, "InstructionId") + " for claim " + claim
                + " was refused by the trailer check before it was sent to the payment vendor: " + reason
                + ".\r\nThe ledger post has been reversed. Correct the remittance before the instruction is re-released.\r\n";
        return new Note("Payment held: " + claim, body);
    }

    static String instructionId(String instruction) throws Exception {
        return child(parse(instruction), "InstructionId");
    }

    private static Element parse(String instruction) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        return factory.newDocumentBuilder().parse(new InputSource(new StringReader(instruction))).getDocumentElement();
    }

    private static String child(Element parent, String name) {
        for (Node n = parent.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element e && name.equals(e.getLocalName())) {
                return e.getTextContent().trim();
            }
        }
        return "";
    }
}
