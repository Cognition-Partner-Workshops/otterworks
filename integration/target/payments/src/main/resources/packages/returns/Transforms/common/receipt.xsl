<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions" exclude-result-prefixes="xs tib">
  <xsl:output method="xml" omit-xml-declaration="yes" indent="no"/>
  <xsl:param name="status" select="'RECEIVED'"/>
  <xsl:template name="status"><xsl:value-of select="$status"/></xsl:template>
  <xsl:template name="amount"><xsl:value-of select="@amount"/></xsl:template>
  <xsl:template name="date"><xsl:value-of select="@timestamp"/></xsl:template>
  <xsl:template match="/"><xsl:apply-templates select="request"/></xsl:template>
  <xsl:template match="request">
    <result id="{@id}" account="{@account}" currency="{@currency}" sequence="{@sequence}">
      <status><xsl:call-template name="status"/></status>
      <amount><xsl:call-template name="amount"/></amount>
      <timestamp><xsl:call-template name="date"/></timestamp>
      <body><xsl:value-of select="concat(@flow,'|',@id,'|',@account,'|')"/><xsl:call-template name="status"/><xsl:text>|</xsl:text><xsl:call-template name="amount"/><xsl:text>|</xsl:text><xsl:call-template name="date"/></body>
    </result>
  </xsl:template>
</xsl:stylesheet>
