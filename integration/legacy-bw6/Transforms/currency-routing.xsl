<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions" exclude-result-prefixes="xs tib">
  <xsl:import href="common/receipt.xsl"/>
  <xsl:param name="status" select="'ROUTED'"/>
  <xsl:template name="status"><xsl:value-of select="if (@currency = 'USD') then 'DOMESTIC' else 'CROSS_BORDER'"/></xsl:template>
</xsl:stylesheet>
