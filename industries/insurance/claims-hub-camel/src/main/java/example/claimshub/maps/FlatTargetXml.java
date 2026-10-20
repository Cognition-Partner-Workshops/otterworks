package example.claimshub.maps;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.SAXException;

/**
 * Reading and writing for the BizTalk instance shape (namespace-qualified root, unqualified children), the way the
 * compiled maps' {@code xsl:value-of} reads and Saxon 12 serialises: no XML declaration, no indentation, an empty
 * value as a self-closed element, and no trailing newline.
 */
final class FlatTargetXml {

    private FlatTargetXml() {
    }

    static Element parseRoot(byte[] source, String namespace, String localName) {
        Element root = parse(source).getDocumentElement();
        if (!namespace.equals(root.getNamespaceURI()) || !localName.equals(root.getLocalName())) {
            throw new IllegalArgumentException("expected root {" + namespace + "}" + localName + " but got {"
                    + root.getNamespaceURI() + "}" + root.getLocalName());
        }
        return root;
    }

    /** The first unqualified child element with this name, or {@code null}. */
    static Element child(Element parent, String localName) {
        for (Node node = parent.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element && element.getNamespaceURI() == null && localName.equals(element.getLocalName())) {
                return element;
            }
        }
        return null;
    }

    /** XPath string value of {@code parent/path[1]}, empty when absent (what {@code xsl:value-of} writes). */
    static String text(Element parent, String... path) {
        Element current = parent;
        for (String step : path) {
            current = child(current, step);
            if (current == null) {
                return "";
            }
        }
        return current.getTextContent();
    }

    static Builder document(String prefix, String namespace, String localName) {
        return new Builder(prefix, namespace, localName);
    }

    static final class Builder {

        private final String qualifiedName;
        private final StringBuilder xml = new StringBuilder();

        private Builder(String prefix, String namespace, String localName) {
            this.qualifiedName = prefix + ":" + localName;
            xml.append('<').append(qualifiedName).append(" xmlns:").append(prefix).append("=\"").append(namespace).append("\">");
        }

        Builder element(String name, String value) {
            if (value.isEmpty()) {
                xml.append('<').append(name).append("/>");
            } else {
                xml.append('<').append(name).append('>');
                escape(value);
                xml.append("</").append(name).append('>');
            }
            return this;
        }

        byte[] toBytes() {
            return (xml + "</" + qualifiedName + ">").getBytes(StandardCharsets.UTF_8);
        }

        private void escape(String value) {
            for (int i = 0; i < value.length(); i++) {
                char c = value.charAt(i);
                switch (c) {
                    case '&' -> xml.append("&amp;");
                    case '<' -> xml.append("&lt;");
                    case '>' -> xml.append("&gt;");
                    case '\r' -> xml.append("&#xD;");
                    default -> xml.append(c);
                }
            }
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
            throw new IllegalArgumentException("source message is not well-formed XML: " + e.getMessage(), e);
        }
    }
}
