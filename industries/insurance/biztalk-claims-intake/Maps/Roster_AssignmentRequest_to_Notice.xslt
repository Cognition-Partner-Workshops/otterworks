<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:var="http://schemas.microsoft.com/BizTalk/2003/var" exclude-result-prefixes="msxsl var s0 s1" version="1.0" xmlns:s0="http://schemas.microsoft.com/BizTalk/2003/aggschema" xmlns:s1="http://schemas.thistlecombe.example/claims/assignment" xmlns:ns0="http://schemas.thistlecombe.example/claims/assignment">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <!-- BizTalk map Roster_AssignmentRequest_to_Notice.btm: two source messages (RosterResult, AssignmentRequest). Picks the available adjuster in the region with the required skill and the fewest open claims, ties broken by adjuster id; with nobody eligible the notice escalates to the claims supervisor. Functoids: Equal, Less Than, Logical AND, Index, Value Mapping, String Concatenate. No scripting. -->
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:Root" />
  </xsl:template>
  <xsl:template match="/s0:Root">
    <xsl:variable name="req" select="InputMessagePart_1/s1:AssignmentRequest" />
    <xsl:variable name="skill" select="$req/RequiredSkill" />
    <xsl:variable name="eligible" select="InputMessagePart_0/s1:RosterResult/Adjuster[Available = 'true' and Region = $req/Region and contains(concat(',', Skills, ','), concat(',', $skill, ',')) and number(OpenClaims) &lt; number(MaxClaims)]" />
    <xsl:variable name="sla">
      <xsl:choose>
        <xsl:when test="$req/Severity = 'HIGH'">1</xsl:when>
        <xsl:when test="$req/Severity = 'MED'">3</xsl:when>
        <xsl:otherwise>7</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <ns0:AssignmentNotice>
      <xsl:choose>
        <xsl:when test="$eligible">
          <xsl:for-each select="$eligible">
            <xsl:sort select="number(OpenClaims)" data-type="number" order="ascending" />
            <xsl:sort select="AdjusterId" order="ascending" />
            <xsl:if test="position() = 1">
              <To><xsl:value-of select="Email" /></To>
              <Subject><xsl:value-of select="concat('Claim ', $req/ClaimNumber, ' assigned: ', $req/LossCause, ' (', $req/Severity, ')')" /></Subject>
              <ClaimNumber><xsl:value-of select="$req/ClaimNumber" /></ClaimNumber>
              <AdjusterId><xsl:value-of select="AdjusterId" /></AdjusterId>
              <AdjusterName><xsl:value-of select="Name" /></AdjusterName>
              <Severity><xsl:value-of select="$req/Severity" /></Severity>
              <SlaDays><xsl:value-of select="$sla" /></SlaDays>
              <Body><xsl:value-of select="concat(Name, ', claim ', $req/ClaimNumber, ' for ', $req/ClaimantName, ' (', $req/LineOfBusiness, ', ', $req/LossCause, ', estimate ', $req/EstimatedAmount, ') is yours. First contact within ', $sla, ' day(s) of ', $req/RequestedDt, '.')" /></Body>
              <Escalated>false</Escalated>
            </xsl:if>
          </xsl:for-each>
        </xsl:when>
        <xsl:otherwise>
          <To>claims.supervisor@thistlecombe.example</To>
          <Subject><xsl:value-of select="concat('Claim ', $req/ClaimNumber, ' needs an adjuster: no capacity in ', $req/Region, ' for ', $skill)" /></Subject>
          <ClaimNumber><xsl:value-of select="$req/ClaimNumber" /></ClaimNumber>
          <AdjusterId>UNASSIGNED</AdjusterId>
          <AdjusterName>Unassigned</AdjusterName>
          <Severity><xsl:value-of select="$req/Severity" /></Severity>
          <SlaDays><xsl:value-of select="$sla" /></SlaDays>
          <Body><xsl:value-of select="concat('No available adjuster in ', $req/Region, ' holds ', $skill, '. Claim ', $req/ClaimNumber, ' for ', $req/ClaimantName, ' waits for manual assignment; SLA is ', $sla, ' day(s) from ', $req/RequestedDt, '.')" /></Body>
          <Escalated>true</Escalated>
        </xsl:otherwise>
      </xsl:choose>
    </ns0:AssignmentNotice>
  </xsl:template>
</xsl:stylesheet>
