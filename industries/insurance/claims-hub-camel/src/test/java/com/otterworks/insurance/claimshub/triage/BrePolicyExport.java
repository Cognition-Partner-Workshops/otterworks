package com.otterworks.insurance.claimshub.triage;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

/** The active rules of a BRE policy export (BRL), read straight from the XML. */
record BrePolicyExport(List<Rule> rules) {

    private static final String BRL = "http://schemas.microsoft.com/businessruleslanguage/2002";

    record Rule(String name, int priority, String outcome, String reason) {
    }

    static BrePolicyExport load(Path policy) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
        Element root = factory.newDocumentBuilder().parse(policy.toFile()).getDocumentElement();
        List<Rule> rules = new ArrayList<>();
        NodeList nodes = root.getElementsByTagNameNS(BRL, "rule");
        for (int i = 0; i < nodes.getLength(); i++) {
            Element rule = (Element) nodes.item(i);
            if (!"true".equals(rule.getAttribute("active"))) {
                continue;
            }
            Element then = first(rule, "then");
            String outcome = null;
            String reason = null;
            NodeList members = then.getElementsByTagNameNS(BRL, "xmldocumentmember");
            for (int m = 0; m < members.getLength(); m++) {
                Element member = (Element) members.item(m);
                if (member.getAttribute("xpath").endsWith("local-name()='Outcome']")) {
                    outcome = first(member, "string").getTextContent();
                }
            }
            NodeList classMembers = then.getElementsByTagNameNS(BRL, "classmember");
            for (int c = 0; c < classMembers.getLength(); c++) {
                Element member = (Element) classMembers.item(c);
                if ("AddReason".equals(member.getAttribute("member"))) {
                    reason = first(member, "string").getTextContent();
                }
            }
            rules.add(new Rule(rule.getAttribute("name"), Integer.parseInt(rule.getAttribute("priority")),
                    outcome, reason));
        }
        return new BrePolicyExport(rules);
    }

    List<String> names() {
        return rules.stream().map(Rule::name).toList();
    }

    private static Element first(Element parent, String localName) {
        return (Element) parent.getElementsByTagNameNS(BRL, localName).item(0);
    }
}
