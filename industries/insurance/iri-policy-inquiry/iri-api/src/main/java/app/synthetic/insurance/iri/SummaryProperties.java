package app.synthetic.insurance.iri;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/** Provisional getPolicySummary values bound from {@code iri.provisional.summary.*}; see sign-offs S-03..S-07. */
@Component
@ConfigurationProperties(prefix = "iri.provisional.summary")
public class SummaryProperties {
    private String carrierId;
    private String issueType;
    private String refreshTimeSource;
    private Map<String, String> productTypes = new LinkedHashMap<>();
    private String planCodeSource;

    public String getCarrierId() { return carrierId; }
    public void setCarrierId(String carrierId) { this.carrierId = carrierId; }
    public String getIssueType() { return issueType; }
    public void setIssueType(String issueType) { this.issueType = issueType; }
    public String getRefreshTimeSource() { return refreshTimeSource; }
    public void setRefreshTimeSource(String refreshTimeSource) { this.refreshTimeSource = refreshTimeSource; }
    public Map<String, String> getProductTypes() { return productTypes; }
    public void setProductTypes(Map<String, String> productTypes) { this.productTypes = productTypes; }
    public String getPlanCodeSource() { return planCodeSource; }
    public void setPlanCodeSource(String planCodeSource) { this.planCodeSource = planCodeSource; }
}
