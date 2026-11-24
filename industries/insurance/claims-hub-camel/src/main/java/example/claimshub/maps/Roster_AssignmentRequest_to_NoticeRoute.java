package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

/** Pure map: the XSLT BizTalk compiled, run as-is under Saxon 12.5. */
@Component
public class Roster_AssignmentRequest_to_NoticeRoute extends RouteBuilder {

    static final String MAP = "Roster_AssignmentRequest_to_Notice";

    @Override
    public void configure() {
        from(MapEndpoints.of(MAP)).routeId(MapEndpoints.routeId(MAP))
                .to("xslt-saxon:maps/" + MAP + ".xslt?output=bytes");
    }
}
