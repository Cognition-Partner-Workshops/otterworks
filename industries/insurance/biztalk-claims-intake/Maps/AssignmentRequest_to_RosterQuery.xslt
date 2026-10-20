<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:var="http://schemas.microsoft.com/BizTalk/2003/var" exclude-result-prefixes="msxsl var s0" version="1.0" xmlns:s0="http://schemas.thistlecombe.example/claims/assignment" xmlns:ns0="http://schemas.thistlecombe.example/claims/assignment">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <!-- BizTalk map AssignmentRequest_to_RosterQuery.btm: three links, no functoids. -->
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:AssignmentRequest" />
  </xsl:template>
  <xsl:template match="/s0:AssignmentRequest">
    <ns0:RosterQuery>
      <Region><xsl:value-of select="Region" /></Region>
      <Skill><xsl:value-of select="RequiredSkill" /></Skill>
      <AsOfDt><xsl:value-of select="RequestedDt" /></AsOfDt>
    </ns0:RosterQuery>
  </xsl:template>
</xsl:stylesheet>
