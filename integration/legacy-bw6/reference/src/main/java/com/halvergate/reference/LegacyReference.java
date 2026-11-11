package com.halvergate.reference;

import com.halvergate.integration.FeeActivities;
import java.io.File;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import javax.xml.transform.stream.StreamSource;
import net.sf.saxon.TransformerFactoryImpl;

public final class LegacyReference {
    private LegacyReference() {}

    public static void main(String[] args) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        factory.setNamespaceAware(true);
        var templates = new TransformerFactoryImpl().newTemplates(new StreamSource(new File(args[0])));
        for (int i = 2; i < args.length; i += 2) {
            var document = factory.newDocumentBuilder().parse(new File(args[i]));
            var request = document.getDocumentElement();
            if (args[1].equals("java-cache")) {
                request.setAttribute("javaAmount", FeeActivities.dailyFee(request.getAttribute("balance"),
                        request.getAttribute("rate"), request.getAttribute("type")));
            } else if (args[1].equals("rounding")) {
                request.setAttribute("javaAmount", FeeActivities.roundHalfEven(request.getAttribute("amount")));
            }
            templates.newTransformer().transform(new DOMSource(document), new StreamResult(new File(args[i + 1])));
        }
    }
}
