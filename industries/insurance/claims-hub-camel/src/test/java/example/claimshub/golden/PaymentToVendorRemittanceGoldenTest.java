package example.claimshub.golden;

/** Payment_to_VendorRemittance (pure XSLT, run under Saxon as the corpus was) against corpus/golden/vendor-remittance. */
class PaymentToVendorRemittanceGoldenTest extends GoldenMapTest {

    @Override
    protected String mapName() {
        return "Payment_to_VendorRemittance";
    }
}
