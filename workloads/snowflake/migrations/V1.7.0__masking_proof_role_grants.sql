-- The run's build user holds READER and ANALYST so proof/masking_side_by_side.py can run the
-- same query under each. The user's DEFAULT_SECONDARY_ROLES is ('ALL'), so the proof runs
-- USE SECONDARY ROLES NONE first; otherwise ANALYST would be active in every session.
GRANT ROLE {{ reader_role }} TO USER {{ env_var('SNOWFLAKE_USER') }};
GRANT ROLE {{ analyst_role }} TO USER {{ env_var('SNOWFLAKE_USER') }};
