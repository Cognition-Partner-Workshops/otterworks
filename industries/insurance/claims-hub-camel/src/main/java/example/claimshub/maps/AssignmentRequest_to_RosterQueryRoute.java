package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

/** BizTalk map AssignmentRequest_to_RosterQuery.btm, run as its compiled XSLT on Saxon. */
@Component
public class AssignmentRequest_to_RosterQueryRoute extends RouteBuilder {

    static final String MAP = "AssignmentRequest_to_RosterQuery";

    @Override
    public void configure() {
        from(MapEndpoints.of(MAP)).routeId(MapEndpoints.routeId(MAP))
                .to("xslt-saxon:maps/" + MAP + ".xslt");
    }
}
