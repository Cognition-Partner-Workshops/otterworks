<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:var="http://schemas.microsoft.com/BizTalk/2003/var" exclude-result-prefixes="msxsl var s0" version="1.0" xmlns:s0="http://schemas.thistlecombe.example/canonical/payment" xmlns:ns0="http://schemas.thistlecombe.example/vendor/remittance">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <!-- BizTalk map Payment_to_VendorRemittance.btm: a Looping functoid drives one Payment record per Line; Record Count, Round and Cumulative Sum (over the rounded cents), Multiplication, Date Format and Value Mapping functoids fill the trailer. Credits (salvage recoveries) are written as absolute cents with indicator C. -->
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:PaymentInstruction" />
  </xsl:template>
  <xsl:template name="cents">
    <xsl:param name="amount" />
    <xsl:choose>
      <xsl:when test="$amount &lt; 0"><xsl:value-of select="format-number(round(-1 * $amount * 100), '0')" /></xsl:when>
      <xsl:otherwise><xsl:value-of select="format-number(round($amount * 100), '0')" /></xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <!-- Cumulative Sum over the Round functoid's output: the trailer adds the cents each PAY record carries, so it always agrees with the body. -->
  <xsl:template name="sumCents">
    <xsl:param name="lines" />
    <xsl:param name="acc" select="0" />
    <xsl:choose>
      <xsl:when test="not($lines)"><xsl:value-of select="format-number($acc, '0')" /></xsl:when>
      <xsl:otherwise>
        <xsl:variable name="first">
          <xsl:call-template name="cents"><xsl:with-param name="amount" select="$lines[1]/Amount" /></xsl:call-template>
        </xsl:variable>
        <xsl:call-template name="sumCents">
          <xsl:with-param name="lines" select="$lines[position() &gt; 1]" />
          <xsl:with-param name="acc" select="$acc + number($first)" />
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="/s0:PaymentInstruction">
    <xsl:variable name="debitCents">
      <xsl:call-template name="sumCents"><xsl:with-param name="lines" select="Line[Amount &gt;= 0]" /></xsl:call-template>
    </xsl:variable>
    <xsl:variable name="creditCents">
      <xsl:call-template name="sumCents"><xsl:with-param name="lines" select="Line[Amount &lt; 0]" /></xsl:call-template>
    </xsl:variable>
    <ns0:Remittance>
      <Header>
        <RecordType>HDR</RecordType>
        <SenderId>THISTLECMB</SenderId>
        <VendorCode><xsl:value-of select="VendorCode" /></VendorCode>
        <FileDate><xsl:value-of select="translate(ValueDate, '-', '')" /></FileDate>
        <InstructionId><xsl:value-of select="InstructionId" /></InstructionId>
        <Currency><xsl:value-of select="CurrencyCd" /></Currency>
      </Header>
      <xsl:for-each select="Line">
        <Payment>
          <RecordType>PAY</RecordType>
          <LineNo><xsl:value-of select="LineNo" /></LineNo>
          <ClaimNumber><xsl:value-of select="../ClaimNumber" /></ClaimNumber>
          <PayeeName><xsl:value-of select="substring(../Payee/Name, 1, 30)" /></PayeeName>
          <PayeeType><xsl:value-of select="../Payee/PayeeType" /></PayeeType>
          <LineType><xsl:value-of select="LineType" /></LineType>
          <AmountCents><xsl:call-template name="cents"><xsl:with-param name="amount" select="Amount" /></xsl:call-template></AmountCents>
          <DebitCreditInd>
            <xsl:choose>
              <xsl:when test="Amount &lt; 0">C</xsl:when>
              <xsl:otherwise>D</xsl:otherwise>
            </xsl:choose>
          </DebitCreditInd>
          <ValueDate><xsl:value-of select="translate(../ValueDate, '-', '')" /></ValueDate>
          <GLAccount><xsl:value-of select="GLAccount" /></GLAccount>
        </Payment>
      </xsl:for-each>
      <Trailer>
        <RecordType>TRL</RecordType>
        <PaymentCount><xsl:value-of select="count(Line)" /></PaymentCount>
        <DebitTotalCents><xsl:value-of select="$debitCents" /></DebitTotalCents>
        <CreditTotalCents><xsl:value-of select="$creditCents" /></CreditTotalCents>
        <HashTotal><xsl:value-of select="format-number((number($debitCents) + number($creditCents)) mod 10000000000, '0')" /></HashTotal>
      </Trailer>
    </ns0:Remittance>
  </xsl:template>
</xsl:stylesheet>
