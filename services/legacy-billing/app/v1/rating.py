"""rating migration boundary (no routes implemented yet).

Add v1 handlers on the supplied blueprint in register(app, blueprint).
Define legacy adapters here and replace only this module's endpoints via
app.view_functions[original_endpoint_name] = adapter inside register.
Registration runs after all legacy rules exist, preserving URLs and url_for.
Adapters bind legacy defaults/form inputs and call the same implementation
as v1, then restore legacy fields/status and add Deprecation/Link headers.
Import shared DB helpers inside handlers to avoid the app import cycle.
No shared registry edits are necessary; this module is auto-discovered.
"""


def register(app, blueprint):
    pass
