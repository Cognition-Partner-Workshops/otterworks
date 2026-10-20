package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

/** {@code Payment_to_LedgerPost}: C# scripting functoids, so a Java transformer instead of XSLT. */
@Component
public class PaymentToLedgerPostRoute extends RouteBuilder {

    static final String MAP = "Payment_to_LedgerPost";

    private final PaymentToLedgerPostTransformer transformer;

    public PaymentToLedgerPostRoute(PaymentToLedgerPostTransformer transformer) {
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
