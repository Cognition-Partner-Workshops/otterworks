-- Commission Pay business logic. All rules live here, in the database, on
-- purpose: this schema is the legacy before-state a modernization extracts from.
WHENEVER SQLERROR EXIT SQL.SQLCODE

CREATE OR REPLACE TYPE split_alloc_t AS OBJECT (
    agent_id  NUMBER,
    split_pct NUMBER
);
/

CREATE OR REPLACE TYPE split_alloc_tab AS TABLE OF split_alloc_t;
/

CREATE OR REPLACE PACKAGE commission_pkg AS

    e_invalid_rate      EXCEPTION;
    e_unknown_agent     EXCEPTION;
    e_inactive_agent    EXCEPTION;
    e_unknown_product   EXCEPTION;
    e_unknown_policy    EXCEPTION;
    e_bad_split         EXCEPTION;
    e_no_rate           EXCEPTION;
    e_policy_not_active EXCEPTION;

    PRAGMA EXCEPTION_INIT(e_invalid_rate,      -20001);
    PRAGMA EXCEPTION_INIT(e_unknown_agent,     -20002);
    PRAGMA EXCEPTION_INIT(e_inactive_agent,    -20003);
    PRAGMA EXCEPTION_INIT(e_unknown_product,   -20004);
    PRAGMA EXCEPTION_INIT(e_unknown_policy,    -20005);
    PRAGMA EXCEPTION_INIT(e_bad_split,         -20006);
    PRAGMA EXCEPTION_INIT(e_no_rate,           -20007);
    PRAGMA EXCEPTION_INIT(e_policy_not_active, -20008);

    -- Create or supersede a commission rate. agent_id NULL sets the product
    -- default. The currently-open rate for the same (product, agent) scope is
    -- closed the day before p_effective_from; history is never deleted.
    PROCEDURE upsert_commission_rate (
        p_product_code   IN commission_rates.product_code%TYPE,
        p_agent_id       IN commission_rates.agent_id%TYPE,
        p_rate_pct       IN commission_rates.rate_pct%TYPE,
        p_effective_from IN DATE,
        p_actor          IN VARCHAR2,
        o_rate_id        OUT commission_rates.rate_id%TYPE
    );

    -- Close the open rate for a (product, agent) scope as of p_effective_to.
    PROCEDURE end_commission_rate (
        p_product_code IN commission_rates.product_code%TYPE,
        p_agent_id     IN commission_rates.agent_id%TYPE,
        p_effective_to IN DATE,
        p_actor        IN VARCHAR2
    );

    -- Replace the split allocation for a policy. Enforces: at least one agent,
    -- no duplicate agents, every agent ACTIVE, percentages each in (0, 100]
    -- and summing to exactly 100.00.
    PROCEDURE set_commission_splits (
        p_policy_id IN policies.policy_id%TYPE,
        p_splits    IN split_alloc_tab,
        p_actor     IN VARCHAR2
    );

    -- Resolve the rate in force for an agent on a product at a given date:
    -- the agent-specific rate wins over the product default.
    FUNCTION resolve_rate (
        p_product_code IN commission_rates.product_code%TYPE,
        p_agent_id     IN commission_rates.agent_id%TYPE,
        p_as_of        IN DATE
    ) RETURN commission_rates.rate_id%TYPE;

    -- Compute the commission ledger rows for a policy for a period (YYYY-MM).
    -- Commission per agent = annual_premium / 12 * rate_pct / 100 * split_pct
    -- / 100, rounded half-up to cents per agent row. Re-running a period for
    -- a policy replaces its rows.
    PROCEDURE calculate_policy_commission (
        p_policy_id    IN policies.policy_id%TYPE,
        p_period_month IN VARCHAR2,
        p_actor        IN VARCHAR2
    );

END commission_pkg;
/

CREATE OR REPLACE PACKAGE BODY commission_pkg AS

    -- The extracted rule owner. Resolvable on the fixture's Compose network;
    -- the network ACL that permits these callouts is granted in
    -- ../setup/02_service_acl.sql.
    c_service_url CONSTANT VARCHAR2(200) := 'http://commission-service:8000';
    c_timeout_s   CONSTANT PLS_INTEGER   := 60;
    c_date_fmt    CONSTANT VARCHAR2(30)  := 'YYYY-MM-DD HH24:MI:SS';

    -- Strangler route: a rule group moves to commission-service when its
    -- procedure body here is replaced by a call_service delegate. Groups not
    -- yet moved keep their PL/SQL rules unchanged below.
    --
    -- Marshals a call to the rule owner and re-raises its verdict. A 200 hands
    -- back the response body; an application error is re-raised with the code
    -- and message the service chose, so callers see the same ORA-20xxx they saw
    -- when the rules ran in this package.
    FUNCTION call_service (
        p_path   IN VARCHAR2,
        p_method IN VARCHAR2,
        p_body   IN VARCHAR2 DEFAULT NULL
    ) RETURN CLOB IS
        l_req    UTL_HTTP.req;
        l_res    UTL_HTTP.resp;
        l_chunk  VARCHAR2(32767);
        l_reply  CLOB;
        l_status PLS_INTEGER;
        l_code   NUMBER;
        l_msg    VARCHAR2(1800);
        l_bytes  RAW(32767);
    BEGIN
        UTL_HTTP.set_transfer_timeout(c_timeout_s);
        l_req := UTL_HTTP.begin_request(c_service_url || p_path, p_method, UTL_HTTP.HTTP_VERSION_1_1);
        UTL_HTTP.set_header(l_req, 'Accept', 'application/json');
        IF p_body IS NOT NULL THEN
            -- Send UTF-8 bytes and declare their exact count; write_text would
            -- convert with the body charset after LENGTHB counted DB bytes.
            l_bytes := UTL_I18N.string_to_raw(p_body, 'AL32UTF8');
            UTL_HTTP.set_header(l_req, 'Content-Type', 'application/json; charset=utf-8');
            UTL_HTTP.set_header(l_req, 'Content-Length', UTL_RAW.length(l_bytes));
            UTL_HTTP.write_raw(l_req, l_bytes);
        ELSE
            UTL_HTTP.set_header(l_req, 'Content-Length', 0);
        END IF;

        l_res := UTL_HTTP.get_response(l_req);
        UTL_HTTP.set_body_charset(l_res, 'UTF-8');
        l_status := l_res.status_code;
        DBMS_LOB.createtemporary(l_reply, TRUE);
        BEGIN
            LOOP
                UTL_HTTP.read_text(l_res, l_chunk, 32767);
                EXIT WHEN l_chunk IS NULL;
                DBMS_LOB.writeappend(l_reply, LENGTH(l_chunk), l_chunk);
            END LOOP;
        EXCEPTION
            WHEN UTL_HTTP.end_of_body THEN NULL;
        END;
        UTL_HTTP.end_response(l_res);

        IF l_status = 200 THEN
            RETURN l_reply;
        END IF;

        l_code := JSON_VALUE(l_reply, '$.ora_code' RETURNING NUMBER);
        l_msg  := NVL(JSON_VALUE(l_reply, '$.message' RETURNING VARCHAR2(1800)),
                      DBMS_LOB.SUBSTR(l_reply, 1000, 1));
        DBMS_LOB.freetemporary(l_reply);
        IF l_code BETWEEN -20999 AND -20001 THEN
            RAISE_APPLICATION_ERROR(l_code, l_msg);
        END IF;
        RAISE_APPLICATION_ERROR(-20000,
            'commission-service HTTP ' || l_status || ': ' || l_msg);
    END call_service;

    PROCEDURE log_action (
        p_action       IN VARCHAR2,
        p_product_code IN VARCHAR2,
        p_agent_id     IN NUMBER,
        p_policy_id    IN NUMBER,
        p_detail       IN VARCHAR2,
        p_actor        IN VARCHAR2
    ) IS
    BEGIN
        INSERT INTO rate_audit_log (action, product_code, agent_id, policy_id, detail, actor)
        VALUES (p_action, p_product_code, p_agent_id, p_policy_id, p_detail, p_actor);
    END log_action;

    PROCEDURE assert_product (p_product_code IN VARCHAR2) IS
        l_count PLS_INTEGER;
    BEGIN
        SELECT COUNT(*) INTO l_count FROM products WHERE product_code = p_product_code;
        IF l_count = 0 THEN
            RAISE_APPLICATION_ERROR(-20004, 'Unknown product: ' || p_product_code);
        END IF;
    END assert_product;

    PROCEDURE assert_active_agent (p_agent_id IN NUMBER) IS
        l_status agents.status%TYPE;
    BEGIN
        BEGIN
            SELECT status INTO l_status FROM agents WHERE agent_id = p_agent_id;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20002, 'Unknown agent: ' || p_agent_id);
        END;
        IF l_status <> 'ACTIVE' THEN
            RAISE_APPLICATION_ERROR(-20003, 'Agent ' || p_agent_id || ' is ' || l_status);
        END IF;
    END assert_active_agent;

    PROCEDURE upsert_commission_rate (
        p_product_code   IN commission_rates.product_code%TYPE,
        p_agent_id       IN commission_rates.agent_id%TYPE,
        p_rate_pct       IN commission_rates.rate_pct%TYPE,
        p_effective_from IN DATE,
        p_actor          IN VARCHAR2,
        o_rate_id        OUT commission_rates.rate_id%TYPE
    ) IS
    BEGIN
        IF p_rate_pct IS NULL OR p_rate_pct <= 0 OR p_rate_pct > 50 THEN
            RAISE_APPLICATION_ERROR(-20001,
                'Rate must be in (0, 50]: ' || NVL(TO_CHAR(p_rate_pct), 'NULL'));
        END IF;
        assert_product(p_product_code);
        IF p_agent_id IS NOT NULL THEN
            assert_active_agent(p_agent_id);
        END IF;

        -- Same-day correction: an open rate that already starts on
        -- p_effective_from is amended in place rather than superseded.
        UPDATE commission_rates
           SET rate_pct = p_rate_pct,
               created_by = p_actor
         WHERE product_code = p_product_code
           AND NVL(agent_id, -1) = NVL(p_agent_id, -1)
           AND effective_to IS NULL
           AND effective_from = p_effective_from
        RETURNING rate_id INTO o_rate_id;

        IF o_rate_id IS NULL THEN
            -- Supersede: close the open rate for this scope the day before
            -- the new one begins.
            UPDATE commission_rates
               SET effective_to = p_effective_from - 1
             WHERE product_code = p_product_code
               AND NVL(agent_id, -1) = NVL(p_agent_id, -1)
               AND effective_to IS NULL
               AND effective_from < p_effective_from;

            INSERT INTO commission_rates
                (product_code, agent_id, rate_pct, effective_from, effective_to, created_by)
            VALUES
                (p_product_code, p_agent_id, p_rate_pct, p_effective_from, NULL, p_actor)
            RETURNING rate_id INTO o_rate_id;
        END IF;

        log_action('RATE_UPSERT', p_product_code, p_agent_id, NULL,
                   'rate_id=' || o_rate_id || ' pct=' || p_rate_pct
                   || ' from=' || TO_CHAR(p_effective_from, 'YYYY-MM-DD'), p_actor);
        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END upsert_commission_rate;

    PROCEDURE end_commission_rate (
        p_product_code IN commission_rates.product_code%TYPE,
        p_agent_id     IN commission_rates.agent_id%TYPE,
        p_effective_to IN DATE,
        p_actor        IN VARCHAR2
    ) IS
    BEGIN
        UPDATE commission_rates
           SET effective_to = p_effective_to
         WHERE product_code = p_product_code
           AND NVL(agent_id, -1) = NVL(p_agent_id, -1)
           AND effective_to IS NULL;
        IF SQL%ROWCOUNT = 0 THEN
            RAISE_APPLICATION_ERROR(-20007,
                'No open rate for ' || p_product_code || '/' || NVL(TO_CHAR(p_agent_id), 'default'));
        END IF;
        log_action('RATE_END', p_product_code, p_agent_id, NULL,
                   'to=' || TO_CHAR(p_effective_to, 'YYYY-MM-DD'), p_actor);
        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END end_commission_rate;

    PROCEDURE set_commission_splits (
        p_policy_id IN policies.policy_id%TYPE,
        p_splits    IN split_alloc_tab,
        p_actor     IN VARCHAR2
    ) IS
        l_item   VARCHAR2(4000);
        l_splits VARCHAR2(32767);
        l_body   VARCHAR2(32767);
        l_reply  CLOB;
    BEGIN
        -- Rules R13-R21 run in commission-service. The allocation travels in
        -- collection order; a NULL collection is sent as null, an empty one as [].
        IF p_splits IS NOT NULL THEN
            l_splits := '[';
            FOR i IN 1 .. p_splits.COUNT LOOP
                SELECT JSON_OBJECT(
                           'agent_id'  VALUE p_splits(i).agent_id,
                           'split_pct' VALUE TO_CHAR(p_splits(i).split_pct)
                           NULL ON NULL RETURNING VARCHAR2(4000))
                  INTO l_item
                  FROM dual;
                l_splits := l_splits || CASE WHEN i > 1 THEN ',' END || l_item;
            END LOOP;
            l_splits := l_splits || ']';
        END IF;

        SELECT JSON_OBJECT(
                   'splits' VALUE l_splits FORMAT JSON,
                   'actor'  VALUE p_actor
                   NULL ON NULL RETURNING VARCHAR2(32767))
          INTO l_body
          FROM dual;
        l_reply := call_service('/policies/' || NVL(TO_CHAR(p_policy_id), 'null') || '/splits',
                                'POST', l_body);
        DBMS_LOB.freetemporary(l_reply);
        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END set_commission_splits;

    FUNCTION resolve_rate (
        p_product_code IN commission_rates.product_code%TYPE,
        p_agent_id     IN commission_rates.agent_id%TYPE,
        p_as_of        IN DATE
    ) RETURN commission_rates.rate_id%TYPE IS
        l_rate_id commission_rates.rate_id%TYPE;
    BEGIN
        -- Agent-specific rate wins over the product default.
        SELECT rate_id INTO l_rate_id
          FROM (SELECT rate_id
                  FROM commission_rates
                 WHERE product_code = p_product_code
                   AND (agent_id = p_agent_id OR agent_id IS NULL)
                   AND effective_from <= p_as_of
                   AND (effective_to IS NULL OR effective_to >= p_as_of)
                 ORDER BY agent_id NULLS LAST, effective_from DESC)
         WHERE ROWNUM = 1;
        RETURN l_rate_id;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20007,
                'No rate in force for ' || p_product_code || '/agent '
                || NVL(TO_CHAR(p_agent_id), 'default') || ' on '
                || TO_CHAR(p_as_of, 'YYYY-MM-DD'));
    END resolve_rate;

    PROCEDURE calculate_policy_commission (
        p_policy_id    IN policies.policy_id%TYPE,
        p_period_month IN VARCHAR2,
        p_actor        IN VARCHAR2
    ) IS
        l_policy  policies%ROWTYPE;
        l_as_of   DATE;
        l_rate_id commission_rates.rate_id%TYPE;
        l_pct     commission_rates.rate_pct%TYPE;
        l_amount  NUMBER;
        l_rows    PLS_INTEGER := 0;
    BEGIN
        BEGIN
            SELECT * INTO l_policy FROM policies WHERE policy_id = p_policy_id;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20005, 'Unknown policy: ' || p_policy_id);
        END;
        IF l_policy.status <> 'IN_FORCE' THEN
            RAISE_APPLICATION_ERROR(-20008,
                'Policy ' || p_policy_id || ' is ' || l_policy.status);
        END IF;

        l_as_of := LAST_DAY(TO_DATE(p_period_month, 'YYYY-MM'));

        DELETE FROM commission_ledger
         WHERE policy_id = p_policy_id AND period_month = p_period_month;

        FOR split IN (SELECT agent_id, split_pct
                        FROM commission_splits
                       WHERE policy_id = p_policy_id
                       ORDER BY split_pct DESC, agent_id) LOOP
            l_rate_id := resolve_rate(l_policy.product_code, split.agent_id, l_as_of);
            SELECT rate_pct INTO l_pct FROM commission_rates WHERE rate_id = l_rate_id;

            l_amount := ROUND(l_policy.annual_premium / 12
                              * l_pct / 100
                              * split.split_pct / 100, 2);

            INSERT INTO commission_ledger
                (policy_id, agent_id, period_month, rate_id, split_pct,
                 base_premium, commission_amt)
            VALUES
                (p_policy_id, split.agent_id, p_period_month, l_rate_id,
                 split.split_pct, l_policy.annual_premium, l_amount);
            l_rows := l_rows + 1;
        END LOOP;

        IF l_rows = 0 THEN
            RAISE_APPLICATION_ERROR(-20006,
                'Policy ' || p_policy_id || ' has no split allocation');
        END IF;

        log_action('COMMISSION_CALC', l_policy.product_code, NULL, p_policy_id,
                   p_period_month || ' rows=' || l_rows, p_actor);
        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END calculate_policy_commission;

END commission_pkg;
/

EXIT;
