package com.otterworks.insurance.claimshub.triage;

import java.io.IOException;
import java.io.StringReader;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;

/** Reads a TriageFacts document into fact name to text, keyed by the children's local names. */
public final class TriageFactsReader {

    private TriageFactsReader() {
    }

    public static Map<String, String> read(String xml) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            factory.setExpandEntityReferences(false);
            DocumentBuilder builder = factory.newDocumentBuilder();
            Element root = builder.parse(new InputSource(new StringReader(xml))).getDocumentElement();
            if (!"TriageFacts".equals(root.getLocalName())) {
                throw new IllegalArgumentException("not a TriageFacts document: " + root.getLocalName());
            }
            Map<String, String> facts = new LinkedHashMap<>();
            for (Node n = root.getFirstChild(); n != null; n = n.getNextSibling()) {
                if (n.getNodeType() == Node.ELEMENT_NODE) {
                    facts.put(n.getLocalName(), n.getTextContent());
                }
            }
            return facts;
        } catch (ParserConfigurationException | SAXException | IOException e) {
            throw new IllegalArgumentException("cannot read TriageFacts", e);
        }
    }
}
