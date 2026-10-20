package example.claimshub.maps;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;

class PaymentToVendorRemittanceTransformerTest {

    private final PaymentToVendorRemittanceTransformer transformer = new PaymentToVendorRemittanceTransformer();

    @Test
    void centsRoundHalfUpLikeXPathRound() {
        assertThat(PaymentToVendorRemittanceTransformer.cents(new BigDecimal("0.015"))).isEqualByComparingTo("2");
        assertThat(PaymentToVendorRemittanceTransformer.cents(new BigDecimal("0.025"))).isEqualByComparingTo("3");
        assertThat(PaymentToVendorRemittanceTransformer.cents(new BigDecimal("0.0249"))).isEqualByComparingTo("2");
        assertThat(PaymentToVendorRemittanceTransformer.cents(new BigDecimal("1234.565"))).isEqualByComparingTo("123457");
        assertThatThrownBy(() -> PaymentToVendorRemittanceTransformer.cents(new BigDecimal("-0.01"))).isInstanceOf(IllegalArgumentException.class);
        assertThat(PaymentToVendorRemittanceTransformer.cents(new BigDecimal("999999.99")).toPlainString()).isEqualTo("99999999");
    }

    @Test
    void creditsAreAbsoluteCentsAndTrailerHashesBothTotals() {
        String out = run(instruction("A &amp; B Collision Repair and Paint Works Ltd",
                line(1, "IND", "12000.00") + line(2, "SAL", "-25000.00")));
        assertThat(out).startsWith("<ns0:Remittance xmlns:ns0=\"http://schemas.thistlecombe.example/vendor/remittance\"><Header>")
                .doesNotEndWith("\n")
                .contains("<PayeeName>A &amp; B Collision Repair and Pai</PayeeName>")
                .contains("<LineNo>2</LineNo>")
                .contains("<AmountCents>2500000</AmountCents><DebitCreditInd>C</DebitCreditInd>")
                .endsWith("<Trailer><RecordType>TRL</RecordType><PaymentCount>2</PaymentCount><DebitTotalCents>1200000</DebitTotalCents>"
                        + "<CreditTotalCents>2500000</CreditTotalCents><HashTotal>3700000</HashTotal></Trailer></ns0:Remittance>");
    }

    @Test
    void rejectsDoctypeAndNonNumericAmounts() {
        assertThatThrownBy(() -> run("<!DOCTYPE x [<!ENTITY e SYSTEM \"file:///etc/passwd\">]>" + instruction("&e;", line(1, "IND", "1.00"))))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> run(instruction("X", line(1, "IND", "n/a")))).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void trailerTotalsAreTheSumOfTheRoundedLines() {
        String out = run(instruction("X", line(1, "IND", "0.006") + line(2, "IND", "0.006") + line(3, "SAL", "-0.006")
                + line(4, "SAL", "-0.005")));
        assertThat(out).contains("<AmountCents>1</AmountCents><DebitCreditInd>D</DebitCreditInd>")
                .endsWith("<PaymentCount>4</PaymentCount><DebitTotalCents>2</DebitTotalCents>"
                        + "<CreditTotalCents>2</CreditTotalCents><HashTotal>4</HashTotal></Trailer></ns0:Remittance>");
    }

    @Test
    void rejectsCharactersXml10DoesNotAllow() {
        assertThatThrownBy(() -> run("<?xml version=\"1.1\"?>" + instruction("A&#x1;B", line(1, "IND", "1.00"))))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("PayeeName contains U+1");
        assertThat(run(instruction("Caf\u00e9 \uD83D\uDE97", line(1, "IND", "1.00")))).contains("<PayeeName>Caf\u00e9 \uD83D\uDE97</PayeeName>");
    }

    private String run(String xml) {
        return new String(transformer.transform(xml.getBytes(StandardCharsets.UTF_8)), StandardCharsets.UTF_8);
    }

    private static String instruction(String payee, String lines) {
        return "<ns0:PaymentInstruction xmlns:ns0=\"http://schemas.thistlecombe.example/canonical/payment\"><InstructionId>PI-1</InstructionId>"
                + "<ClaimNumber>CLM-1</ClaimNumber><VendorCode>PAYV01</VendorCode><Payee><Name>" + payee + "</Name><PayeeType>VN</PayeeType></Payee>"
                + "<ValueDate>2026-10-08</ValueDate><CurrencyCd>USD</CurrencyCd>" + lines + "</ns0:PaymentInstruction>";
    }

    private static String line(int no, String type, String amount) {
        return "<Line><LineNo>" + no + "</LineNo><LineType>" + type + "</LineType><Amount>" + amount + "</Amount><GLAccount>61010100</GLAccount></Line>";
    }
}
