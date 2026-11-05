"""Serves the locator through waitress: a fixed worker pool and an idle timeout,
so slow or idle clients cannot hold an unbounded number of threads."""

SERVE_OPTIONS = {
    "threads": 4,
    "connection_limit": 100,
    "channel_timeout": 30,
    "cleanup_interval": 10,
    "asyncore_use_poll": True,
    "ident": "branch-locator",
}


def serve(app, host, port, **overrides):
    import waitress

    options = dict(SERVE_OPTIONS)
    options.update(overrides)
    waitress.serve(app, host=host, port=port, **options)
