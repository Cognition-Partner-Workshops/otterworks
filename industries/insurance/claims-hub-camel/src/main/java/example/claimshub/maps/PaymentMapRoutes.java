package example.claimshub.maps;

import example.claimshub.MapEndpoints;
import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

/**
 * The two maps ClaimPayment.odx calls, kept as XSLT and run by Saxon. Payment_to_VendorRemittance is pure
 * XSLT 1.0 and is the BizTalk stylesheet unchanged; Payment_to_LedgerPost uses the corpus's golden twin, where
 * the C# scripting functoids are XSLT 3.0 functions.
 */
@Component
public class PaymentMapRoutes extends RouteBuilder {

    public static final String LEDGER_POST = "Payment_to_LedgerPost";
    public static final String VENDOR_REMITTANCE = "Payment_to_VendorRemittance";

    @Override
    public void configure() {
        from(MapEndpoints.of(LEDGER_POST)).routeId(MapEndpoints.routeId(LEDGER_POST))
                .to("xslt-saxon:maps/Payment_to_LedgerPost.golden.xslt");
        from(MapEndpoints.of(VENDOR_REMITTANCE)).routeId(MapEndpoints.routeId(VENDOR_REMITTANCE))
                .to("xslt-saxon:maps/Payment_to_VendorRemittance.xslt");
    }
}
