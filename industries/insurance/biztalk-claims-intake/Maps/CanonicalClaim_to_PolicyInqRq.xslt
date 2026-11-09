<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:var="http://schemas.microsoft.com/BizTalk/2003/var" exclude-result-prefixes="msxsl var s0" version="1.0" xmlns:s0="http://schemas.thistlecombe.example/canonical/claim" xmlns:ns0="http://schemas.thistlecombe.example/acord/policy">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <!-- BizTalk map CanonicalClaim_to_PolicyInqRq.btm: three links, no functoids. -->
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:Claim" />
  </xsl:template>
  <xsl:template match="/s0:Claim">
    <ns0:PolicyInqRq>
      <RqUID><xsl:value-of select="SourceRqUID" /></RqUID>
      <PolicyNumber><xsl:value-of select="PolicyNumber" /></PolicyNumber>
      <AsOfDt><xsl:value-of select="Loss/LossDate" /></AsOfDt>
    </ns0:PolicyInqRq>
  </xsl:template>
</xsl:stylesheet>
