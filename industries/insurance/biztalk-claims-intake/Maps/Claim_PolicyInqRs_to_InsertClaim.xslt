<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:var="http://schemas.microsoft.com/BizTalk/2003/var" exclude-result-prefixes="msxsl var s0 s1 s2" version="1.0" xmlns:s0="http://schemas.microsoft.com/BizTalk/2003/aggschema" xmlns:s1="http://schemas.thistlecombe.example/canonical/claim" xmlns:s2="http://schemas.thistlecombe.example/acord/policy" xmlns:ns0="http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <!-- BizTalk map Claim_PolicyInqRs_to_InsertClaim.btm: two source messages (canonical Claim, PolicyInqRs). Functoids: Less Than, Greater Than, Logical AND, Subtraction, Minimum, Value Mapping. No scripting. -->
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:Root" />
  </xsl:template>
  <xsl:template match="/s0:Root">
    <xsl:variable name="c" select="InputMessagePart_0/s1:Claim" />
    <xsl:variable name="p" select="InputMessagePart_1/s2:PolicyInqRs" />
    <xsl:variable name="lossNum" select="number(translate($c/Loss/LossDate, '-', ''))" />
    <xsl:variable name="effNum" select="number(translate($p/EffectiveDt, '-', ''))" />
    <xsl:variable name="expNum" select="number(translate($p/ExpirationDt, '-', ''))" />
    <xsl:variable name="est" select="number($c/Loss/EstimatedAmount)" />
    <xsl:variable name="limit" select="number($p/CoverageLimitAmt)" />
    <xsl:variable name="ded" select="number($p/DeductibleAmt)" />
    <xsl:variable name="capped">
      <xsl:choose>
        <xsl:when test="$est &lt; $limit"><xsl:value-of select="$est" /></xsl:when>
        <xsl:otherwise><xsl:value-of select="$limit" /></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="net">
      <xsl:choose>
        <xsl:when test="number($capped) - $ded &gt; 0"><xsl:value-of select="number($capped) - $ded" /></xsl:when>
        <xsl:otherwise>0</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <ns0:usp_InsertClaim>
      <ClaimNumber><xsl:value-of select="$c/ClaimNumber" /></ClaimNumber>
      <PolicyNumber><xsl:value-of select="$p/PolicyNumber" /></PolicyNumber>
      <PolicyStatus><xsl:value-of select="$p/PolicyStatusCd" /></PolicyStatus>
      <PolicyEffectiveDate><xsl:value-of select="$p/EffectiveDt" /></PolicyEffectiveDate>
      <LineOfBusiness><xsl:value-of select="$p/LOBCd" /></LineOfBusiness>
      <InsuredPartyId><xsl:value-of select="$p/InsuredPartyId" /></InsuredPartyId>
      <ClaimantName><xsl:value-of select="$c/Claimant/FullName" /></ClaimantName>
      <xsl:choose>
        <xsl:when test="$c/Claimant/TaxIdMasked">
          <ClaimantTaxIdMasked><xsl:value-of select="$c/Claimant/TaxIdMasked" /></ClaimantTaxIdMasked>
        </xsl:when>
        <xsl:otherwise>
          <ClaimantTaxIdMasked xsi:nil="true" />
        </xsl:otherwise>
      </xsl:choose>
      <LossDate><xsl:value-of select="$c/Loss/LossDate" /></LossDate>
      <ReportedDate><xsl:value-of select="$c/Loss/ReportedDate" /></ReportedDate>
      <LossCause><xsl:value-of select="$c/Loss/CauseCode" /></LossCause>
      <LossDescription><xsl:value-of select="$c/Loss/Description" /></LossDescription>
      <EstimatedAmount><xsl:value-of select="format-number($est, '0.00')" /></EstimatedAmount>
      <Deductible><xsl:value-of select="format-number($ded, '0.00')" /></Deductible>
      <CoverageLimit><xsl:value-of select="format-number($limit, '0.00')" /></CoverageLimit>
      <NetExposure><xsl:value-of select="format-number($net, '0.00')" /></NetExposure>
      <InjuryFlag><xsl:value-of select="$c/Loss/Injury" /></InjuryFlag>
      <PriorFraudFlag><xsl:value-of select="$c/Claimant/PriorFraudFlag" /></PriorFraudFlag>
      <InForceAtLoss>
        <xsl:choose>
          <xsl:when test="$p/PolicyStatusCd = 'Active' and $lossNum &gt;= $effNum and $lossNum &lt;= $expNum">true</xsl:when>
          <xsl:otherwise>false</xsl:otherwise>
        </xsl:choose>
      </InForceAtLoss>
      <AgencyId><xsl:value-of select="$c/Agency/Id" /></AgencyId>
      <TriageOutcome xsi:nil="true" />
    </ns0:usp_InsertClaim>
  </xsl:template>
</xsl:stylesheet>
