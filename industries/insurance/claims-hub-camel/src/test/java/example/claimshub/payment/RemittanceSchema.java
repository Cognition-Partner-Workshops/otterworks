package example.claimshub.payment;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import javax.xml.parsers.DocumentBuilderFactory;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import example.claimshub.golden.CorpusManifest;

/** The positional layout as Schemas/PaymentVendor_Remittance_FF.xsd declares it, read from the schema itself. */
final class RemittanceSchema {

    static final String XS = "http://www.w3.org/2001/XMLSchema";
    static final String B = "http://schemas.microsoft.com/BizTalk/2003";

    record Field(String name, int offset, int length, boolean right, char pad) {

        String slice(String record) {
            return record.substring(offset, offset + length);
        }
    }

    record Record(String element, String tag, List<Field> fields) {

        int length() {
            return fields.stream().mapToInt(Field::length).sum();
        }
    }

    private RemittanceSchema() {
    }

    static Path path() {
        return CorpusManifest.fixtureDir().resolve("Schemas/PaymentVendor_Remittance_FF.xsd");
    }

    /** Records keyed by tag ({@code HDR}, {@code PAY}, {@code TRL}), in schema order. */
    static Map<String, Record> load() {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            Document doc = factory.newDocumentBuilder().parse(path().toFile());
            Map<String, Record> records = new LinkedHashMap<>();
            NodeList infos = doc.getElementsByTagNameNS(B, "recordInfo");
            for (int i = 0; i < infos.getLength(); i++) {
                Element info = (Element) infos.item(i);
                if (!"positional".equals(info.getAttribute("structure"))) {
                    continue;
                }
                Element record = (Element) info.getParentNode().getParentNode().getParentNode();
                List<Field> fields = new ArrayList<>();
                NodeList fieldInfos = record.getElementsByTagNameNS(B, "fieldInfo");
                for (int j = 0; j < fieldInfos.getLength(); j++) {
                    Element f = (Element) fieldInfos.item(j);
                    Element field = (Element) f.getParentNode().getParentNode().getParentNode();
                    String pad = f.getAttribute("pad_char");
                    fields.add(new Field(field.getAttribute("name"), Integer.parseInt(f.getAttribute("pos_offset")),
                            Integer.parseInt(f.getAttribute("pos_length")), "right".equals(f.getAttribute("justification")),
                            pad.isEmpty() ? ' ' : pad.charAt(0)));
                }
                records.put(info.getAttribute("tag_name"), new Record(record.getAttribute("name"), info.getAttribute("tag_name"), fields));
            }
            return records;
        } catch (Exception e) {
            throw new IllegalStateException("cannot read " + path(), e);
        }
    }
}
