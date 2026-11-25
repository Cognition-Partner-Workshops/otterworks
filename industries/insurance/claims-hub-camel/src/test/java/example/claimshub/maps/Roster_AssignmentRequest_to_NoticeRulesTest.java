package example.claimshub.maps;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.StringReader;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;

import javax.xml.transform.stream.StreamSource;

import org.apache.camel.Exchange;
import org.apache.camel.ProducerTemplate;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import example.claimshub.ClaimsHubApplication;
import example.claimshub.MapEndpoints;
import example.claimshub.golden.CorpusManifest;
import net.sf.saxon.s9api.Processor;
import net.sf.saxon.s9api.Serializer;
import net.sf.saxon.s9api.XsltTransformer;

/**
 * Cases the corpus does not reach, each checked twice: against the expectation read from the map, and byte
 * for byte against the BizTalk map's own XSLT run under Saxon, so the Java side is held to the legacy map
 * and not to this test's reading of it.
 */
@SpringBootTest(classes = ClaimsHubApplication.class, properties = {"camel.springboot.main-run-controller=false", "camel.component.direct.timeout=2000"})
class Roster_AssignmentRequest_to_NoticeRulesTest {

    private static final String MAP = "Roster_AssignmentRequest_to_Notice";

    @Autowired
    ProducerTemplate producer;

    @Test
    void tieOnOpenClaimsGoesToTheLowestAdjusterIdWhateverTheRosterOrder() throws Exception {
        String notice = sameAsLegacy(aggregate("HIGH", "AUTO-PD",
                adjuster("ADJ-205", "COASTAL", "AUTO-PD", 4, 20, true),
                adjuster("ADJ-203", "COASTAL", "AUTO-PD,PROPERTY", 4, 20, true),
                adjuster("ADJ-204", "COASTAL", "AUTO-PD", 6, 20, true)));
        assertThat(notice).contains("<AdjusterId>ADJ-203</AdjusterId>").contains("<Escalated>false</Escalated>");
    }

    @Test
    void leastLoadedIsComparedAsANumberNotAsText() throws Exception {
        String notice = sameAsLegacy(aggregate("MED", "AUTO-PD",
                adjuster("ADJ-301", "COASTAL", "AUTO-PD", 10, 20, true),
                adjuster("ADJ-302", "COASTAL", "AUTO-PD", 9, 20, true)));
        assertThat(notice).contains("<AdjusterId>ADJ-302</AdjusterId>");
    }

    @Test
    void unavailableAtCapacityOtherRegionAndPartialSkillAreNotEligible() throws Exception {
        String notice = sameAsLegacy(aggregate("LOW", "AUTO-PD",
                adjuster("ADJ-401", "COASTAL", "AUTO-PD", 0, 20, false),
                adjuster("ADJ-402", "COASTAL", "AUTO-PD", 20, 20, true),
                adjuster("ADJ-403", "INLAND", "AUTO-PD", 0, 20, true),
                adjuster("ADJ-404", "COASTAL", "AUTO-PDX,XAUTO-PD", 0, 20, true),
                adjuster("ADJ-405", "COASTAL", "PROPERTY,AUTO-PD", 15, 20, true)));
        assertThat(notice).contains("<AdjusterId>ADJ-405</AdjusterId>");
    }

    @Test
    void nobodyEligibleEscalatesToTheSupervisorWithEscalatedTrue() throws Exception {
        String notice = sameAsLegacy(aggregate("HIGH", "LIABILITY",
                adjuster("ADJ-501", "COASTAL", "LIABILITY", 22, 22, true)));
        assertThat(notice).contains("<To>claims.supervisor@thistlecombe.example</To>")
                .contains("<AdjusterId>UNASSIGNED</AdjusterId>").contains("<Escalated>true</Escalated>");
    }

    @Test
    void slaDaysAreOneThreeAndSevenAndAnyOtherSeverityIsSeven() throws Exception {
        assertThat(sameAsLegacy(aggregate("HIGH", "AUTO-PD", adjuster("ADJ-601", "COASTAL", "AUTO-PD", 1, 9, true)))).contains("<SlaDays>1</SlaDays>");
        assertThat(sameAsLegacy(aggregate("MED", "AUTO-PD", adjuster("ADJ-601", "COASTAL", "AUTO-PD", 1, 9, true)))).contains("<SlaDays>3</SlaDays>");
        assertThat(sameAsLegacy(aggregate("LOW", "AUTO-PD", adjuster("ADJ-601", "COASTAL", "AUTO-PD", 1, 9, true)))).contains("<SlaDays>7</SlaDays>");
        assertThat(sameAsLegacy(aggregate("CRITICAL", "AUTO-PD", adjuster("ADJ-601", "COASTAL", "AUTO-PD", 1, 9, true)))).contains("<SlaDays>7</SlaDays>");
        assertThat(sameAsLegacy(aggregate("high", "LIABILITY", adjuster("ADJ-601", "COASTAL", "AUTO-PD", 1, 9, true)))).contains("<SlaDays>7</SlaDays>");
    }

    @Test
    void markupInNamesIsEscapedTheWaySaxonSerialisesIt() throws Exception {
        String agg = aggregate("LOW", "AUTO-PD", adjuster("ADJ-701", "COASTAL", "AUTO-PD", 1, 9, true))
                .replace("Claimant Name", "O'Hara &amp; Sons &lt;Ltd&gt; \"Q\"");
        assertThat(sameAsLegacy(agg)).contains("O'Hara &amp; Sons &lt;Ltd&gt; \"Q\"");
    }

    private String sameAsLegacy(String aggregate) throws Exception {
        String legacy = legacyXslt(aggregate);
        Exchange result = producer.request(MapEndpoints.of(MAP), e -> e.getIn().setBody(aggregate.getBytes(StandardCharsets.UTF_8)));
        if (result.getException() != null) {
            throw result.getException();
        }
        String actual = new String(result.getMessage().getMandatoryBody(byte[].class), StandardCharsets.UTF_8);
        assertThat(actual).isEqualTo(legacy);
        return actual;
    }

    private static String legacyXslt(String aggregate) throws Exception {
        Path xslt = CorpusManifest.fixtureDir().resolve("Maps/" + MAP + ".xslt");
        Processor saxon = new Processor(false);
        XsltTransformer t = saxon.newXsltCompiler().compile(new StreamSource(xslt.toFile())).load();
        t.setSource(new StreamSource(new StringReader(aggregate)));
        StringWriter out = new StringWriter();
        Serializer serializer = saxon.newSerializer(out);
        t.setDestination(serializer);
        t.transform();
        return out.toString();
    }

    private static String adjuster(String id, String region, String skills, int open, int max, boolean available) {
        return "<Adjuster><AdjusterId>" + id + "</AdjusterId><Name>Name " + id + "</Name><Email>" + id.toLowerCase()
                + "@thistlecombe.example</Email><Region>" + region + "</Region><Skills>" + skills + "</Skills><OpenClaims>"
                + open + "</OpenClaims><MaxClaims>" + max + "</MaxClaims><Available>" + available + "</Available></Adjuster>";
    }

    private static String aggregate(String severity, String skill, String... adjusters) {
        return "<ns0:Root xmlns:ns0=\"http://schemas.microsoft.com/BizTalk/2003/aggschema\"><InputMessagePart_0>"
                + "<ns1:RosterResult xmlns:ns1=\"http://schemas.thistlecombe.example/claims/assignment\">" + String.join("", adjusters)
                + "</ns1:RosterResult></InputMessagePart_0><InputMessagePart_1>"
                + "<ns1:AssignmentRequest xmlns:ns1=\"http://schemas.thistlecombe.example/claims/assignment\"><RequestId>ASG-599999</RequestId>"
                + "<ClaimNumber>CLM-2026-199999</ClaimNumber><LineOfBusiness>AUTO</LineOfBusiness><LossCause>COLL</LossCause>"
                + "<Region>COASTAL</Region><Severity>" + severity + "</Severity><RequiredSkill>" + skill + "</RequiredSkill>"
                + "<RequestedDt>2026-11-02</RequestedDt><ClaimantName>Claimant Name</ClaimantName>"
                + "<EstimatedAmount>1500.00</EstimatedAmount></ns1:AssignmentRequest></InputMessagePart_1></ns0:Root>";
    }
}
