<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions" exclude-result-prefixes="xs tib">
  <xsl:import href="../../common/receipt.xsl"/>
  <xsl:function name="tib:parse-dateTime" as="xs:dateTime"><xsl:param name="value"/><xsl:sequence select="xs:dateTime($value)"/></xsl:function>
  <xsl:function name="tib:format-dateTime" as="xs:string"><xsl:param name="value" as="xs:dateTime"/><xsl:param name="zone"/><xsl:sequence select="if ($zone = 'UTC') then string(adjust-dateTime-to-timezone($value,xs:dayTimeDuration('PT0H'))) else error()"/></xsl:function>
</xsl:stylesheet>
