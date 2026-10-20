package example.claimshub.maps;

import java.io.ByteArrayInputStream;
import java.io.IOException;
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
 * The BizTalk aggregate envelope a two-source map reads ({@code aggschema} Root with
 * {@code InputMessagePart_0}, {@code InputMessagePart_1}, ...), with the XPath 1.0 string semantics the
 * compiled maps rely on: a missing node reads as the empty string.
 */
final class AggregateEnvelope {

    static final String AGG_NS = "http://schemas.microsoft.com/BizTalk/2003/aggschema";

    private final Element root;

    private AggregateEnvelope(Element root) {
        this.root = root;
    }

    static AggregateEnvelope parse(byte[] xml) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            factory.setXIncludeAware(false);
            factory.setExpandEntityReferences(false);
            DocumentBuilder builder = factory.newDocumentBuilder();
            Document doc = builder.parse(new ByteArrayInputStream(xml));
            Element root = doc.getDocumentElement();
            if (!AGG_NS.equals(root.getNamespaceURI()) || !"Root".equals(root.getLocalName())) {
                throw new IllegalArgumentException("not a BizTalk aggregate envelope: {" + root.getNamespaceURI() + "}" + root.getLocalName());
            }
            return new AggregateEnvelope(root);
        } catch (ParserConfigurationException | SAXException | IOException e) {
            throw new IllegalArgumentException("cannot parse aggregate envelope: " + e.getMessage(), e);
        }
    }

    /** {@code InputMessagePart_<index>/ns:<localName>}, or null when absent. */
    Element part(int index, String namespace, String localName) {
        Element part = child(root, null, "InputMessagePart_" + index);
        return part == null ? null : child(part, namespace, localName);
    }

    /** First child element with the given (null for unqualified) namespace and local name, or null. */
    static Element child(Element parent, String namespace, String localName) {
        if (parent == null) {
            return null;
        }
        for (Node n = parent.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element e && matches(e, namespace, localName)) {
                return e;
            }
        }
        return null;
    }

    static List<Element> children(Element parent, String localName) {
        List<Element> out = new ArrayList<>();
        if (parent == null) {
            return out;
        }
        for (Node n = parent.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element e && matches(e, null, localName)) {
                out.add(e);
            }
        }
        return out;
    }

    /** XPath 1.0 {@code string()} of an unqualified path below {@code start}; empty when any step is missing. */
    static String text(Element start, String... path) {
        Element e = start;
        for (String step : path) {
            e = child(e, null, step);
            if (e == null) {
                return "";
            }
        }
        return e == null ? "" : e.getTextContent();
    }

    static boolean exists(Element start, String... path) {
        Element e = start;
        for (String step : path) {
            e = child(e, null, step);
            if (e == null) {
                return false;
            }
        }
        return e != null;
    }

    private static boolean matches(Element e, String namespace, String localName) {
        String ns = e.getNamespaceURI();
        boolean nsMatch = namespace == null ? ns == null || ns.isEmpty() : namespace.equals(ns);
        return nsMatch && localName.equals(e.getLocalName());
    }
}
