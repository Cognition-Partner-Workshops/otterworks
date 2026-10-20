<?xml version="1.0" encoding="UTF-8"?>
<!-- Golden twin of InsertClaim_to_TriageFacts.xslt for the Saxon corpus run. Same links, same output; the two C# scripting functoids are reproduced as XSLT 3.0 functions. ComputeReserve keeps .NET Math.Round semantics (half to even). -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" exclude-result-prefixes="xs s0 f" version="3.0" xmlns:s0="http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo" xmlns:ns0="http://schemas.thistlecombe.example/claims/triage" xmlns:f="urn:claims-hub:golden">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <xsl:function name="f:ComputeReserve" as="xs:string">
    <xsl:param name="estimatedAmount" as="xs:string" />
    <xsl:param name="lossCause" as="xs:string" />
    <xsl:param name="injuryFlag" as="xs:string" />
    <xsl:variable name="estimate" select="xs:decimal($estimatedAmount)" />
    <xsl:variable name="base" as="xs:decimal">
      <xsl:choose>
        <xsl:when test="$lossCause = 'COLL'">1.10</xsl:when>
        <xsl:when test="$lossCause = 'COMP'">1.00</xsl:when>
        <xsl:when test="$lossCause = 'GLAS'">0.85</xsl:when>
        <xsl:when test="$lossCause = 'THFT'">1.25</xsl:when>
        <xsl:when test="$lossCause = 'FIRE'">1.40</xsl:when>
        <xsl:when test="$lossCause = 'WATR'">1.30</xsl:when>
        <xsl:when test="$lossCause = 'WIND'">1.15</xsl:when>
        <xsl:when test="$lossCause = 'LIAB'">1.60</xsl:when>
        <xsl:otherwise>1.00</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="factor" select="if ($injuryFlag = 'true') then $base + 0.35 else $base" />
    <xsl:sequence select="format-number(round-half-to-even($estimate * $factor, 2), '0.00')" />
  </xsl:function>
  <xsl:function name="f:DaysBetween" as="xs:string">
    <xsl:param name="fromDate" as="xs:string" />
    <xsl:param name="toDate" as="xs:string" />
    <xsl:sequence select="string(days-from-duration(xs:date($toDate) - xs:date($fromDate)))" />
  </xsl:function>
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:usp_InsertClaim" />
  </xsl:template>
  <xsl:template match="/s0:usp_InsertClaim">
    <ns0:TriageFacts>
      <ClaimNumber><xsl:value-of select="ClaimNumber" /></ClaimNumber>
      <LossCause><xsl:value-of select="LossCause" /></LossCause>
      <EstimatedAmount><xsl:value-of select="EstimatedAmount" /></EstimatedAmount>
      <ReserveEstimate><xsl:value-of select="f:ComputeReserve(string(EstimatedAmount), string(LossCause), string(InjuryFlag))" /></ReserveEstimate>
      <ReportDelayDays><xsl:value-of select="f:DaysBetween(string(LossDate), string(ReportedDate))" /></ReportDelayDays>
      <PolicyAgeDaysAtLoss><xsl:value-of select="f:DaysBetween(string(PolicyEffectiveDate), string(LossDate))" /></PolicyAgeDaysAtLoss>
      <InjuryFlag><xsl:value-of select="InjuryFlag" /></InjuryFlag>
      <PriorFraudFlag><xsl:value-of select="PriorFraudFlag" /></PriorFraudFlag>
      <InForceAtLoss><xsl:value-of select="InForceAtLoss" /></InForceAtLoss>
      <NetExposure><xsl:value-of select="NetExposure" /></NetExposure>
    </ns0:TriageFacts>
  </xsl:template>
</xsl:stylesheet>
