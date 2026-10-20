package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

/** {@code InsertClaim_to_TriageFacts}: C# scripting functoids, so a Java transformer instead of XSLT. */
@Component
public class InsertClaimToTriageFactsRoute extends RouteBuilder {

    static final String MAP = "InsertClaim_to_TriageFacts";

    private final InsertClaimToTriageFactsTransformer transformer;

    public InsertClaimToTriageFactsRoute(InsertClaimToTriageFactsTransformer transformer) {
        this.transformer = transformer;
    }

    @Override
    public void configure() {
        from(MapEndpoints.of(MAP))
                .routeId(MapEndpoints.routeId(MAP))
                .process(exchange -> exchange.getMessage().setBody(
                        transformer.transform(exchange.getIn().getMandatoryBody(byte[].class))));
    }
}
