package example.claimshub.maps;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

import example.claimshub.MapEndpoints;

/** Payment_to_VendorRemittance as a Java transformer: the map's functoids carry rounding and totals logic. */
@Component
public class PaymentToVendorRemittanceRoute extends RouteBuilder {

    static final String MAP = "Payment_to_VendorRemittance";

    private final PaymentToVendorRemittanceTransformer transformer = new PaymentToVendorRemittanceTransformer();

    @Override
    public void configure() {
        from(MapEndpoints.of(MAP))
                .routeId(MapEndpoints.routeId(MAP))
                .process(exchange -> exchange.getMessage().setBody(transformer.transform(exchange.getMessage().getMandatoryBody(byte[].class))));
    }
}
