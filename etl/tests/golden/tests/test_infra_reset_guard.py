import pytest

from harness import infra, settings

OPT_IN = {settings.RESET_OPT_IN_ENV: "1"}


@pytest.fixture
def endpoints(monkeypatch):
    def set_endpoints(localstack, meili, pg_host):
        monkeypatch.setattr(settings, "LOCALSTACK_URL", localstack)
        monkeypatch.setattr(settings, "MEILI_URL", meili)
        monkeypatch.setattr(settings, "PG_HOST", pg_host)

    return set_endpoints


@pytest.mark.parametrize(
    "localstack, meili, pg_host",
    [
        ("http://localhost:4566", "http://localhost:7700", "localhost"),
        ("http://127.0.0.1:4566", "http://[::1]:7700", "127.0.0.1"),
        ("http://localstack:4566", "http://meilisearch:7700", "postgres"),
        ("http://LOCALHOST:4566", "http://localhost:7700", "localhost"),
    ],
)
def test_local_endpoints_with_opt_in_are_allowed(endpoints, localstack, meili, pg_host):
    endpoints(localstack, meili, pg_host)
    infra.check_reset_allowed(OPT_IN)


def test_missing_opt_in_is_refused(endpoints):
    endpoints("http://localhost:4566", "http://localhost:7700", "localhost")
    for env in (
        {},
        {settings.RESET_OPT_IN_ENV: "0"},
        {settings.RESET_OPT_IN_ENV: "true"},
    ):
        with pytest.raises(infra.ResetRefused, match=settings.RESET_OPT_IN_ENV):
            infra.check_reset_allowed(env)


@pytest.mark.parametrize(
    "localstack, meili, pg_host, refused",
    [
        (
            "https://s3.us-east-1.amazonaws.com",
            "http://localhost:7700",
            "localhost",
            "GOLDEN_LOCALSTACK_URL",
        ),
        (
            "http://localhost.evil.example:4566",
            "http://localhost:7700",
            "localhost",
            "GOLDEN_LOCALSTACK_URL",
        ),
        (
            "http://localhost:4566",
            "https://search.example.com",
            "localhost",
            "GOLDEN_MEILI_URL",
        ),
        (
            "http://localhost:4566",
            "http://localhost:7700",
            "db.example.com",
            "GOLDEN_PG_HOST",
        ),
        ("not a url", "http://localhost:7700", "localhost", "GOLDEN_LOCALSTACK_URL"),
    ],
)
def test_remote_endpoint_is_refused_even_with_opt_in(
    endpoints, localstack, meili, pg_host, refused
):
    endpoints(localstack, meili, pg_host)
    with pytest.raises(infra.ResetRefused, match=refused):
        infra.check_reset_allowed(OPT_IN)


def test_reset_checks_before_touching_any_store(endpoints, monkeypatch):
    endpoints("https://s3.amazonaws.com", "http://localhost:7700", "localhost")
    monkeypatch.setenv(settings.RESET_OPT_IN_ENV, "1")

    def no_client(*_args, **_kwargs):
        raise AssertionError("reset touched a store before the guard")

    for name in ("s3", "dynamodb", "sqs", "pg_connect", "meili"):
        monkeypatch.setattr(infra, name, no_client)
    with pytest.raises(infra.ResetRefused):
        infra.reset()
