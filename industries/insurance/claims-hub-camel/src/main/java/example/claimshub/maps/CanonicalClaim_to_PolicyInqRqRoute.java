package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

/** BizTalk map CanonicalClaim_to_PolicyInqRq.btm, run as its compiled XSLT on Saxon. */
@Component
public class CanonicalClaim_to_PolicyInqRqRoute extends RouteBuilder {

    static final String MAP = "CanonicalClaim_to_PolicyInqRq";

    @Override
    public void configure() {
        from(MapEndpoints.of(MAP)).routeId(MapEndpoints.routeId(MAP))
                .to("xslt-saxon:maps/" + MAP + ".xslt");
    }
}
