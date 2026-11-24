package example.claimshub.golden;

import static org.assertj.core.api.Assertions.assertThat;

import org.apache.camel.builder.RouteBuilder;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;

import example.claimshub.MapEndpoints;

/**
 * Proves the harness end to end without converting a map: an identity route fed with the goldens of
 * CanonicalClaim_to_PolicyInqRq must reproduce them byte for byte through Camel.
 */
class GoldenMapTestSelfTest extends GoldenMapTest {

    private static final String IDENTITY = "__identity";

    @BeforeAll
    void addIdentityRoute() throws Exception {
        camelContext.addRoutes(new RouteBuilder() {
            @Override
            public void configure() {
                from(MapEndpoints.of(IDENTITY)).routeId(MapEndpoints.routeId(IDENTITY)).convertBodyTo(byte[].class);
            }
        });
    }

    @Override
    protected String mapName() {
        return IDENTITY;
    }

    @Override
    protected CorpusManifest.MapSpec spec() {
        CorpusManifest.MapSpec real = CorpusManifest.load().map("CanonicalClaim_to_PolicyInqRq");
        return new CorpusManifest.MapSpec(IDENTITY, real.xslt(), real.golden(), real.golden(), real.suffix());
    }

    @AfterAll
    void everyGoldenRoundTrips() {
        assertThat(rows()).hasSize(16).allMatch(Row::identical);
    }
}
