package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

@Component
public class RosterAssignmentRequestToNoticeRoute extends RouteBuilder {

    public static final String MAP = "Roster_AssignmentRequest_to_Notice";

    private final RosterAssignmentRequestToNoticeTransformer transformer = new RosterAssignmentRequestToNoticeTransformer();

    @Override
    public void configure() {
        from(MapEndpoints.of(MAP)).routeId(MapEndpoints.routeId(MAP))
                .convertBodyTo(byte[].class)
                .process(exchange -> exchange.getMessage().setBody(transformer.transform(exchange.getMessage().getBody(byte[].class))));
    }
}
