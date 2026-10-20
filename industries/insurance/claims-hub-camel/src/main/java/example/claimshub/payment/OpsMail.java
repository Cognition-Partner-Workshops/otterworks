package example.claimshub.payment;

import java.io.StringReader;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;

/** ThistlecombeMutual.ClaimsHub.Helpers.OpsMail.PaymentHeld(msgInstruction, attempts). */
public final class OpsMail {

    private OpsMail() {
    }

    public record Note(String subject, String body) {
    }

    public static Note paymentHeld(String instruction, int attempts) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element root = factory.newDocumentBuilder().parse(new InputSource(new StringReader(instruction))).getDocumentElement();
        String instructionId = child(root, "InstructionId");
        String claim = child(root, "ClaimNumber");
        String body = "Payment instruction " + instructionId + " for claim " + claim + " was not delivered to the payment vendor after "
                + attempts + " attempts.\r\nThe ledger post has been reversed. Re-release the instruction once the vendor is reachable.\r\n";
        return new Note("Payment held: " + claim, body);
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
