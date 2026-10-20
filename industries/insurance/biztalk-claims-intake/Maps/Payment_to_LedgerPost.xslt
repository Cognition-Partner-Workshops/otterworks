<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:var="http://schemas.microsoft.com/BizTalk/2003/var" exclude-result-prefixes="msxsl var s0 userCSharp" version="1.0" xmlns:s0="http://schemas.thistlecombe.example/canonical/payment" xmlns:ns0="http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo" xmlns:userCSharp="http://schemas.microsoft.com/BizTalk/2003/userCSharp">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <!-- BizTalk map Payment_to_LedgerPost.btm: Scripting functoids (inline C#) build the vendor reference with its mod-97 check digits and format the ledger amounts with the invariant culture. The golden twin Payment_to_LedgerPost.golden.xslt reproduces them in XSLT 3.0. -->
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:PaymentInstruction" />
  </xsl:template>
  <xsl:template match="/s0:PaymentInstruction">
    <ns0:usp_PostClaimPayment>
      <InstructionId><xsl:value-of select="InstructionId" /></InstructionId>
      <ClaimNumber><xsl:value-of select="ClaimNumber" /></ClaimNumber>
      <VendorReference><xsl:value-of select="userCSharp:MakeVendorReference(string(InstructionId), string(ClaimNumber))" /></VendorReference>
      <PayeeName><xsl:value-of select="Payee/Name" /></PayeeName>
      <ValueDate><xsl:value-of select="ValueDate" /></ValueDate>
      <Currency><xsl:value-of select="CurrencyCd" /></Currency>
      <IndemnityAmount><xsl:value-of select="userCSharp:FormatMoney(string(sum(Line[LineType='IND']/Amount)))" /></IndemnityAmount>
      <ExpenseAmount><xsl:value-of select="userCSharp:FormatMoney(string(sum(Line[LineType='EXP']/Amount)))" /></ExpenseAmount>
      <SalvageCredit><xsl:value-of select="userCSharp:FormatMoney(string(-1 * sum(Line[LineType='SLV']/Amount)))" /></SalvageCredit>
      <NetAmount><xsl:value-of select="userCSharp:FormatMoney(string(sum(Line/Amount)))" /></NetAmount>
      <LineCount><xsl:value-of select="count(Line)" /></LineCount>
    </ns0:usp_PostClaimPayment>
  </xsl:template>
  <msxsl:script language="C#" implements-prefix="userCSharp"><![CDATA[
// Vendor reference: claim number without hyphens plus the last six characters of the instruction id,
// upper-cased, followed by two ISO 7064 mod 97-10 check digits computed the IBAN way (letters A..Z become 10..35).
public string MakeVendorReference(string instructionId, string claimNumber)
{
    string body = (claimNumber.Replace("-", "") + instructionId.Substring(instructionId.Length - 6)).ToUpperInvariant();
    System.Text.StringBuilder digits = new System.Text.StringBuilder();
    foreach (char c in body + "00")
    {
        if (char.IsLetter(c)) { digits.Append(((int)(c - 'A') + 10).ToString()); }
        else { digits.Append(c); }
    }
    int remainder = 0;
    foreach (char d in digits.ToString())
    {
        remainder = (remainder * 10 + (d - '0')) % 97;
    }
    int check = 98 - remainder;
    return body + "-" + check.ToString("00", System.Globalization.CultureInfo.InvariantCulture);
}

// Money is written with two decimals and a dot whatever the host culture; the ledger procedure parses it back.
public string FormatMoney(string amount)
{
    decimal value = System.Convert.ToDecimal(amount, System.Globalization.CultureInfo.InvariantCulture);
    return System.Math.Round(value, 2).ToString("0.00", System.Globalization.CultureInfo.InvariantCulture);
}
]]></msxsl:script>
</xsl:stylesheet>
