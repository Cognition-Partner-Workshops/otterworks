package example.claimshub.orchestrations;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.Date;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.Statement;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

import javax.xml.parsers.DocumentBuilderFactory;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

/**
 * Loads {@code corpus/stubs/roster} into PostgreSQL: each stub is what the WCF-SQL roster port answered for
 * one request, so its rows are stored as the region's roster as of that request's {@code RequestedDt}.
 */
public final class RosterStubSeed {

    public record Adjuster(String adjusterId, String name, String email, String region, String skills,
            int openClaims, int maxClaims, boolean available) {
    }

    private RosterStubSeed() {
    }

    public static void load(Path fixture, String url, String user, String password) throws Exception {
        try (Connection db = DriverManager.getConnection(url, user, password)) {
            try (Statement ddl = db.createStatement()) {
                ddl.execute(new String(RosterStubSeed.class.getResourceAsStream("/roster/schema.sql").readAllBytes(), StandardCharsets.UTF_8));
            }
            try (PreparedStatement insert = db.prepareStatement(
                    "INSERT INTO adjuster_roster VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)");
                    Stream<Path> stubs = Files.list(fixture.resolve("corpus/stubs/roster"))) {
                for (Path stub : stubs.sorted().toList()) {
                    LocalDate asOf = LocalDate.parse(text(parse(fixture.resolve("corpus/inputs/assignment").resolve(stub.getFileName())), "RequestedDt"));
                    for (Adjuster a : adjusters(stub)) {
                        insert.setDate(1, Date.valueOf(asOf));
                        insert.setString(2, a.adjusterId());
                        insert.setString(3, a.name());
                        insert.setString(4, a.email());
                        insert.setString(5, a.region());
                        insert.setString(6, a.skills());
                        insert.setInt(7, a.openClaims());
                        insert.setInt(8, a.maxClaims());
                        insert.setBoolean(9, a.available());
                        insert.addBatch();
                    }
                }
                insert.executeBatch();
            }
        }
    }

    public static List<Adjuster> adjusters(Path stub) throws Exception {
        NodeList nodes = parse(stub).getElementsByTagName("Adjuster");
        List<Adjuster> out = new ArrayList<>();
        for (int i = 0; i < nodes.getLength(); i++) {
            Element e = (Element) nodes.item(i);
            out.add(new Adjuster(child(e, "AdjusterId"), child(e, "Name"), child(e, "Email"), child(e, "Region"),
                    child(e, "Skills"), Integer.parseInt(child(e, "OpenClaims")), Integer.parseInt(child(e, "MaxClaims")),
                    Boolean.parseBoolean(child(e, "Available"))));
        }
        return out;
    }

    static Document parse(Path file) throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setNamespaceAware(true);
        return f.newDocumentBuilder().parse(file.toFile());
    }

    static String text(Document doc, String element) {
        return doc.getElementsByTagName(element).item(0).getTextContent();
    }

    private static String child(Element parent, String name) {
        return parent.getElementsByTagName(name).item(0).getTextContent();
    }
}
