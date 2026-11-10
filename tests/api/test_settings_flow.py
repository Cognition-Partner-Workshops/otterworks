import pytest


pytestmark = pytest.mark.api_flow

NOTIFICATION_TOGGLES = ("notificationEmail", "notificationInApp", "notificationDesktop")


def test_settings_page_reads_defaults_and_persists_notification_toggles(api_client):
    user = api_client.register_user("settings-flow")

    initial = api_client.client.get("/api/v1/settings", headers=user.auth_headers)
    api_client.assert_gateway_route_available(initial, "/api/v1/settings")
    assert initial.status_code == 200, initial.text
    assert {key: initial.json()[key] for key in NOTIFICATION_TOGGLES} == {
        "notificationEmail": True,
        "notificationInApp": True,
        "notificationDesktop": False,
    }

    expected = dict(initial.json())
    for toggle in NOTIFICATION_TOGGLES:
        expected[toggle] = not expected[toggle]
        response = api_client.client.patch(
            "/api/v1/settings",
            headers=user.auth_headers,
            json={toggle: expected[toggle]},
        )
        assert response.status_code == 200, response.text
        assert {key: response.json()[key] for key in NOTIFICATION_TOGGLES} == {
            key: expected[key] for key in NOTIFICATION_TOGGLES
        }

    reloaded = api_client.client.get("/api/v1/settings", headers=user.auth_headers)
    assert reloaded.status_code == 200, reloaded.text
    assert {key: reloaded.json()[key] for key in NOTIFICATION_TOGGLES} == {
        key: expected[key] for key in NOTIFICATION_TOGGLES
    }


def test_settings_are_scoped_to_the_caller(api_client):
    alice = api_client.register_user("settings-alice")
    bob = api_client.register_user("settings-bob")

    update = api_client.client.patch(
        "/api/v1/settings",
        headers=alice.auth_headers,
        json={"notificationEmail": False},
    )
    assert update.status_code == 200, update.text

    bob_settings = api_client.client.get("/api/v1/settings", headers=bob.auth_headers)
    assert bob_settings.status_code == 200, bob_settings.text
    assert bob_settings.json()["notificationEmail"] is True


def test_settings_require_authentication_and_reject_malformed_body(api_client):
    assert api_client.client.get("/api/v1/settings").status_code == 401
    assert (
        api_client.client.patch("/api/v1/settings", json={"notificationEmail": False}).status_code
        == 401
    )

    user = api_client.register_user("settings-malformed")
    malformed = api_client.client.patch(
        "/api/v1/settings",
        headers=user.auth_headers,
        json={"notificationEmail": "not-a-boolean"},
    )
    assert malformed.status_code == 400, malformed.text
    api_client.assert_json_error(malformed)
