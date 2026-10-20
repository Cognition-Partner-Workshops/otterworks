package example.claimshub.maps;

import java.util.Map;

import example.claimshub.golden.GoldenMapTest;

class Payment_to_VendorRemittanceGoldenTest extends GoldenMapTest {

    private static final String EXPONENT = "golden is Saxon's xs:double serialisation of XPath round(): cents of 1000000 or more are written in exponent notation (%s); the transformer writes BigDecimal integer cents (%s)";

    @Override
    protected String mapName() {
        return "Payment_to_VendorRemittance";
    }

    @Override
    protected Map<String, String> knownCauses() {
        return Map.of(
                "PI-2026-880100.xml", EXPONENT.formatted("HashTotal 1.07069E6", "1070690"),
                "PI-2026-880102.xml", EXPONENT.formatted("line 1 AmountCents 1.112507E6, DebitTotalCents and HashTotal 1.154046E6", "1112507, 1154046"),
                "PI-2026-880103.xml", EXPONENT.formatted("line 1 AmountCents and DebitTotalCents 1.063E6, HashTotal 1.141247E6", "1063000, 1141247"),
                "PI-2026-880105.xml", EXPONENT.formatted("AmountCents, DebitTotalCents and HashTotal 1.033155E6", "1033155"),
                "PI-2026-880107.xml", "rounding: line 2 Amount 1234.565 is 123456.5 cents; the golden has 123457 (XPath round(), half toward positive infinity, over xs:double), the transformer 123456 (.NET Math.Round, RoundingMode.HALF_EVEN); trailer DebitTotalCents 123508 agrees",
                "PI-2026-880108.xml", EXPONENT.formatted("line 1 AmountCents 1.110149E6, DebitTotalCents and HashTotal 1.141819E6", "1110149, 1141819"),
                "PI-2026-880110.xml", EXPONENT.formatted("line 1 AmountCents 1.4272E6, DebitTotalCents and HashTotal 1.469282E6", "1427200, 1469282"),
                "PI-2026-880111.xml", EXPONENT.formatted("AmountCents 9.9999999E7, 1.2E6 and 2.5E6, DebitTotalCents 1.01199999E8, CreditTotalCents 2.5E6, HashTotal 1.03699999E8", "99999999, 1200000, 2500000, 101199999, 2500000, 103699999"),
                "PI-2026-880113.xml", EXPONENT.formatted("AmountCents, DebitTotalCents and HashTotal 1.051525E6", "1051525"));
    }
}
