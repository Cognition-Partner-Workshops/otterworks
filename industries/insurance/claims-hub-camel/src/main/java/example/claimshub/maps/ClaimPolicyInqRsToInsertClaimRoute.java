package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

@Component
public class ClaimPolicyInqRsToInsertClaimRoute extends RouteBuilder {

    public static final String MAP = "Claim_PolicyInqRs_to_InsertClaim";

    private final ClaimPolicyInqRsToInsertClaimTransformer transformer = new ClaimPolicyInqRsToInsertClaimTransformer();

    @Override
    public void configure() {
        from(MapEndpoints.of(MAP)).routeId(MapEndpoints.routeId(MAP))
                .convertBodyTo(byte[].class)
                .process(exchange -> exchange.getMessage().setBody(transformer.transform(exchange.getMessage().getBody(byte[].class))));
    }
}
