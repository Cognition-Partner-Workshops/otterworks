package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

/** BizTalk map Fnol_to_CanonicalClaim.btm, run as its compiled XSLT on Saxon. */
@Component
public class Fnol_to_CanonicalClaimRoute extends RouteBuilder {

    static final String MAP = "Fnol_to_CanonicalClaim";

    @Override
    public void configure() {
        from(MapEndpoints.of(MAP)).routeId(MapEndpoints.routeId(MAP))
                .to("xslt-saxon:maps/" + MAP + ".xslt");
    }
}
