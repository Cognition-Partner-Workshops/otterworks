package example.claimshub;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

// The ClaimTriage rules table (#2089) lives in its own package; the hub scans it for the Call_Rules shape.
@SpringBootApplication(scanBasePackages = {"example.claimshub", "com.otterworks.insurance.claimshub.triage"})
public class ClaimsHubApplication {

    public static void main(String[] args) {
        SpringApplication.run(ClaimsHubApplication.class, args);
    }
}
