<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:var="http://schemas.microsoft.com/BizTalk/2003/var" exclude-result-prefixes="msxsl var s0" version="1.0" xmlns:s0="http://schemas.thistlecombe.example/acord/claims/fnol" xmlns:ns0="http://schemas.thistlecombe.example/canonical/claim">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <!-- BizTalk map Fnol_to_CanonicalClaim.btm: links plus String Concatenate, String Extract and Value Mapping functoids. No scripting. -->
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:ClaimsSvcRq" />
  </xsl:template>
  <xsl:template match="/s0:ClaimsSvcRq">
    <xsl:variable name="rq" select="ClaimsNotificationAddRq" />
    <ns0:Claim>
      <ClaimNumber><xsl:value-of select="$rq/ClaimsOccurrence/ClaimNumber" /></ClaimNumber>
      <SourceRqUID><xsl:value-of select="RqUID" /></SourceRqUID>
      <Agency>
        <Id><xsl:value-of select="$rq/Producer/ProducerId" /></Id>
        <Name><xsl:value-of select="$rq/Producer/ProducerName" /></Name>
      </Agency>
      <PolicyNumber><xsl:value-of select="$rq/Policy/PolicyNumber" /></PolicyNumber>
      <LineOfBusiness><xsl:value-of select="$rq/Policy/LOBCd" /></LineOfBusiness>
      <Claimant>
        <FullName><xsl:value-of select="concat($rq/InsuredOrPrincipal/GivenName, ' ', $rq/InsuredOrPrincipal/Surname)" /></FullName>
        <xsl:if test="$rq/InsuredOrPrincipal/TaxId">
          <xsl:variable name="tax" select="$rq/InsuredOrPrincipal/TaxId" />
          <TaxIdMasked><xsl:value-of select="concat('***-**-', substring($tax, string-length($tax) - 3))" /></TaxIdMasked>
        </xsl:if>
        <xsl:if test="$rq/InsuredOrPrincipal/PhoneNumber">
          <Phone><xsl:value-of select="$rq/InsuredOrPrincipal/PhoneNumber" /></Phone>
        </xsl:if>
        <xsl:if test="$rq/InsuredOrPrincipal/EmailAddr">
          <Email><xsl:value-of select="$rq/InsuredOrPrincipal/EmailAddr" /></Email>
        </xsl:if>
        <PriorFraudFlag>
          <xsl:choose>
            <xsl:when test="$rq/InsuredOrPrincipal/PriorFraudFlagInd = 'true' or $rq/InsuredOrPrincipal/PriorFraudFlagInd = '1'">true</xsl:when>
            <xsl:otherwise>false</xsl:otherwise>
          </xsl:choose>
        </PriorFraudFlag>
      </Claimant>
      <Loss>
        <LossDate><xsl:value-of select="$rq/ClaimsOccurrence/LossDt" /></LossDate>
        <ReportedDate><xsl:value-of select="$rq/ClaimsOccurrence/ReportedDt" /></ReportedDate>
        <CauseCode><xsl:value-of select="$rq/ClaimsOccurrence/LossCauseCd" /></CauseCode>
        <Description><xsl:value-of select="normalize-space($rq/ClaimsOccurrence/IncidentDesc)" /></Description>
        <EstimatedAmount><xsl:value-of select="format-number($rq/ClaimsOccurrence/EstimatedLossAmt, '0.00')" /></EstimatedAmount>
        <Injury><xsl:value-of select="$rq/ClaimsOccurrence/InjuryInd" /></Injury>
        <PoliceReport>
          <xsl:choose>
            <xsl:when test="$rq/ClaimsOccurrence/PoliceReportInd = 'true'">true</xsl:when>
            <xsl:otherwise>false</xsl:otherwise>
          </xsl:choose>
        </PoliceReport>
        <City><xsl:value-of select="$rq/ClaimsOccurrence/Addr/City" /></City>
        <State><xsl:value-of select="$rq/ClaimsOccurrence/Addr/StateProvCd" /></State>
        <PostalCode><xsl:value-of select="$rq/ClaimsOccurrence/Addr/PostalCode" /></PostalCode>
      </Loss>
      <xsl:if test="$rq/AutoLossInfo">
        <Vehicle>
          <VIN><xsl:value-of select="$rq/AutoLossInfo/VIN" /></VIN>
          <Driveable><xsl:value-of select="$rq/AutoLossInfo/DriveableInd" /></Driveable>
        </Vehicle>
      </xsl:if>
    </ns0:Claim>
  </xsl:template>
</xsl:stylesheet>
