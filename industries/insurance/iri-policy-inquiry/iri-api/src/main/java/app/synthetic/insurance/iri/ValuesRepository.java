package app.synthetic.insurance.iri;

import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class ValuesRepository {
    private final JdbcTemplate jdbc;

    public ValuesRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Map<String, Object>> find(long contract) {
        return jdbc.queryForList("SELECT * FROM policy_values WHERE contract_no = ?", contract).stream().findFirst();
    }
}
