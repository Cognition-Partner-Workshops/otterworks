package com.halvergate.customeralerts.packages.alerts;

import java.io.StringReader;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.xml.sax.InputSource;

record AlertRecord(String id, String account, String currency, String amount, String status, String body,
                   boolean filtered) {
    static AlertRecord parse(String xml) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setNamespaceAware(true);
        Element root = factory.newDocumentBuilder().parse(new InputSource(new StringReader(xml)))
            .getDocumentElement();
        return new AlertRecord(root.getAttribute("id"), root.getAttribute("account"),
            root.getAttribute("currency"), text(root, "amount"), text(root, "status"),
            text(root, "body"), root.hasAttribute("filtered"));
    }

    private static String text(Element root, String name) {
        var node = root.getElementsByTagName(name).item(0);
        return node == null ? "" : node.getTextContent();
    }
}
