package example.claimshub.orchestrations;

import java.util.List;
import java.util.Map;

/** The roster rows the JDBC endpoint returns, as the RosterResult message the WCF-SQL port answered with. */
public final class RosterResultXml {

    private static final String[][] COLUMNS = {
        {"adjuster_id", "AdjusterId"}, {"name", "Name"}, {"email", "Email"}, {"region", "Region"},
        {"skills", "Skills"}, {"open_claims", "OpenClaims"}, {"max_claims", "MaxClaims"}, {"available", "Available"},
    };

    private RosterResultXml() {
    }

    public static String of(List<Map<String, Object>> rows) {
        StringBuilder xml = new StringBuilder("<ns0:RosterResult xmlns:ns0=\"" + AdjusterAssignmentRoute.NS + "\">");
        for (Map<String, Object> row : rows) {
            xml.append("<Adjuster>");
            for (String[] c : COLUMNS) {
                Object value = row.get(c[0]);
                if (value == null) {
                    throw new IllegalStateException("roster row without " + c[0] + ": " + row);
                }
                xml.append('<').append(c[1]).append('>').append(escape(String.valueOf(value))).append("</").append(c[1]).append('>');
            }
            xml.append("</Adjuster>");
        }
        return xml.append("</ns0:RosterResult>").toString();
    }

    static String escape(String s) {
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
