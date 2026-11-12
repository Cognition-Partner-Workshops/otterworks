package app.synthetic.insurance;

import java.util.List;
import java.util.Map;
import java.util.Optional;

public interface InquiryRepository {
    Optional<Map<String, Object>> summary(long contract);
    Optional<Map<String, Object>> values(long contract);
    List<Map<String, Object>> funds(long contract);
    List<Long> contracts();
    void ping();
}
