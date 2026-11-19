<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="xml" indent="no" omit-xml-declaration="yes"/>
  <xsl:param name="Suffix" select="''"/>
  <xsl:template match="/greeting">
    <shout><xsl:value-of select="concat(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), $Suffix)"/></shout>
  </xsl:template>
</xsl:stylesheet>
