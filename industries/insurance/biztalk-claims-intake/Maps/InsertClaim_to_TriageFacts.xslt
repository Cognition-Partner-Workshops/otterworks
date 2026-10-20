<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:var="http://schemas.microsoft.com/BizTalk/2003/var" exclude-result-prefixes="msxsl var s0 userCSharp" version="1.0" xmlns:s0="http://schemas.microsoft.com/Sql/2008/05/TypedProcedures/dbo" xmlns:ns0="http://schemas.thistlecombe.example/claims/triage" xmlns:userCSharp="http://schemas.microsoft.com/BizTalk/2003/userCSharp">
  <xsl:output omit-xml-declaration="yes" method="xml" version="1.0" />
  <!-- BizTalk map InsertClaim_to_TriageFacts.btm: two Scripting functoids (inline C#) carry the reserve rule and the day counts. The golden twin InsertClaim_to_TriageFacts.golden.xslt reproduces them in XSLT 3.0. -->
  <xsl:template match="/">
    <xsl:apply-templates select="/s0:usp_InsertClaim" />
  </xsl:template>
  <xsl:template match="/s0:usp_InsertClaim">
    <ns0:TriageFacts>
      <ClaimNumber><xsl:value-of select="ClaimNumber" /></ClaimNumber>
      <LossCause><xsl:value-of select="LossCause" /></LossCause>
      <EstimatedAmount><xsl:value-of select="EstimatedAmount" /></EstimatedAmount>
      <ReserveEstimate><xsl:value-of select="userCSharp:ComputeReserve(string(EstimatedAmount), string(LossCause), string(InjuryFlag))" /></ReserveEstimate>
      <ReportDelayDays><xsl:value-of select="userCSharp:DaysBetween(string(LossDate), string(ReportedDate))" /></ReportDelayDays>
      <PolicyAgeDaysAtLoss><xsl:value-of select="userCSharp:DaysBetween(string(PolicyEffectiveDate), string(LossDate))" /></PolicyAgeDaysAtLoss>
      <InjuryFlag><xsl:value-of select="InjuryFlag" /></InjuryFlag>
      <PriorFraudFlag><xsl:value-of select="PriorFraudFlag" /></PriorFraudFlag>
      <InForceAtLoss><xsl:value-of select="InForceAtLoss" /></InForceAtLoss>
      <NetExposure><xsl:value-of select="NetExposure" /></NetExposure>
    </ns0:TriageFacts>
  </xsl:template>
  <msxsl:script language="C#" implements-prefix="userCSharp"><![CDATA[
// Reserve rule: the initial reserve is the agency estimate scaled by a factor per loss cause,
// plus 35 points when anyone was hurt. Rounded to cents with Math.Round, which rounds half to even.
public string ComputeReserve(string estimatedAmount, string lossCause, string injuryFlag)
{
    decimal estimate = System.Convert.ToDecimal(estimatedAmount, System.Globalization.CultureInfo.InvariantCulture);
    decimal factor;
    switch (lossCause)
    {
        case "COLL": factor = 1.10m; break;
        case "COMP": factor = 1.00m; break;
        case "GLAS": factor = 0.85m; break;
        case "THFT": factor = 1.25m; break;
        case "FIRE": factor = 1.40m; break;
        case "WATR": factor = 1.30m; break;
        case "WIND": factor = 1.15m; break;
        case "LIAB": factor = 1.60m; break;
        default: factor = 1.00m; break;
    }
    if (injuryFlag == "true") { factor += 0.35m; }
    decimal reserve = System.Math.Round(estimate * factor, 2);
    return reserve.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture);
}

public string DaysBetween(string fromDate, string toDate)
{
    System.DateTime from = System.DateTime.ParseExact(fromDate, "yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture);
    System.DateTime to = System.DateTime.ParseExact(toDate, "yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture);
    return ((int)(to - from).TotalDays).ToString(System.Globalization.CultureInfo.InvariantCulture);
}
]]></msxsl:script>
</xsl:stylesheet>
