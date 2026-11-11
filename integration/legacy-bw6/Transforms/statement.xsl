<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions" exclude-result-prefixes="xs tib">
  <xsl:import href="statements/layout.xsl"/>
  <xsl:param name="status" select="'STATEMENT_READY'"/>
  <xsl:template name="date"><xsl:value-of select="tib:format-dateTime(tib:parse-dateTime(@timestamp),'UTC')"/></xsl:template>
</xsl:stylesheet>
