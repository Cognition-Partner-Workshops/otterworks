<?xml version="1.0" encoding="UTF-8"?>
<!-- Golden twin of Payment_to_LedgerPost.xslt for the Saxon corpus run. The C# scripting functoids are reproduced as XSLT 3.0 functions: mod 97-10 check digits over the IBAN letter mapping, money formatted as 0.00 with half-to-even rounding on the summed decimals. -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" exclude-result-prefixes="xs s0 f" version="3.0" xmlns:s0="http://schemas.thistlecombe.example/canonical/payment" xmlns:ns0="http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo" xmlns:f="urn:claims-hub:golden">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <xsl:function name="f:MakeVendorReference" as="xs:string">
    <xsl:param name="instructionId" as="xs:string" />
    <xsl:param name="claimNumber" as="xs:string" />
    <xsl:variable name="body" select="upper-case(concat(replace($claimNumber, '-', ''), substring($instructionId, string-length($instructionId) - 5)))" />
    <xsl:variable name="digits" select="string-join(for $cp in string-to-codepoints(concat($body, '00')) return if ($cp ge 65 and $cp le 90) then string($cp - 55) else codepoints-to-string($cp), '')" />
    <xsl:variable name="remainder" select="fold-left(for $cp in string-to-codepoints($digits) return $cp - 48, 0, function($acc, $d) { ($acc * 10 + $d) mod 97 })" />
    <xsl:sequence select="concat($body, '-', format-number(98 - $remainder, '00'))" />
  </xsl:function>
  <xsl:function name="f:FormatMoney" as="xs:string">
    <xsl:param name="amount" as="xs:decimal" />
    <xsl:sequence select="format-number(round-half-to-even($amount, 2), '0.00')" />
  </xsl:function>
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:PaymentInstruction" />
  </xsl:template>
  <xsl:template match="/s0:PaymentInstruction">
    <ns0:usp_PostClaimPayment>
      <InstructionId><xsl:value-of select="InstructionId" /></InstructionId>
      <ClaimNumber><xsl:value-of select="ClaimNumber" /></ClaimNumber>
      <VendorReference><xsl:value-of select="f:MakeVendorReference(string(InstructionId), string(ClaimNumber))" /></VendorReference>
      <PayeeName><xsl:value-of select="Payee/Name" /></PayeeName>
      <ValueDate><xsl:value-of select="ValueDate" /></ValueDate>
      <Currency><xsl:value-of select="CurrencyCd" /></Currency>
      <IndemnityAmount><xsl:value-of select="f:FormatMoney(sum(Line[LineType='IND']/xs:decimal(Amount)))" /></IndemnityAmount>
      <ExpenseAmount><xsl:value-of select="f:FormatMoney(sum(Line[LineType='EXP']/xs:decimal(Amount)))" /></ExpenseAmount>
      <SalvageCredit><xsl:value-of select="f:FormatMoney(-1 * sum(Line[LineType='SLV']/xs:decimal(Amount)))" /></SalvageCredit>
      <NetAmount><xsl:value-of select="f:FormatMoney(sum(Line/xs:decimal(Amount)))" /></NetAmount>
      <LineCount><xsl:value-of select="count(Line)" /></LineCount>
    </ns0:usp_PostClaimPayment>
  </xsl:template>
</xsl:stylesheet>
