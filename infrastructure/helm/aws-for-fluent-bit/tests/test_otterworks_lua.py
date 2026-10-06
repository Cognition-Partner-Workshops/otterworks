"""Unit tests for otterworks.lua on LuaJIT (the Fluent Bit Lua runtime).

    python3 -m pip install --user lupa
    python3 -m unittest discover -s infrastructure/helm/aws-for-fluent-bit/tests
"""
import pathlib
import unittest

try:
    from lupa import luajit21 as lupa_rt
except ImportError:  # pragma: no cover - lupa built without LuaJIT
    try:
        from lupa import lua51 as lupa_rt
    except ImportError:
        lupa_rt = None

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "otterworks.lua"


@unittest.skipIf(lupa_rt is None, "lupa is not installed")
class RouteRecordTest(unittest.TestCase):
    def setUp(self):
        self.lua = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(SCRIPT.read_text())
        self.route = self.lua.globals().route_record

    def call(self, record):
        def to_lua(v):
            return self.lua.table_from({k: to_lua(x) for k, x in v.items()}) if isinstance(v, dict) else v
        code, ts, out = self.route("kube.x", 1.5, to_lua(record))
        return code, ts, (dict(out.items()) if code == 2 else None)

    def test_api_gateway_access_line_routes_to_tenant_group(self):
        code, ts, out = self.call({"route": "/api/v1/files/:id", "status": 200,
                                   "kubernetes": {"container_name": "api-gateway", "namespace_name": "otterworks-t1"}})
        self.assertEqual((code, ts), (2, 1.5))
        self.assertEqual(out["cw_group"], "otterworks-t1/api-gateway")

    def test_api_gateway_non_access_line_is_dropped(self):
        code, _, _ = self.call({"msg": "starting", "kubernetes": {"container_name": "api-gateway", "namespace_name": "otterworks-t1"}})
        self.assertEqual(code, -1)

    def test_ingress_line_is_filed_under_upstream_tenant(self):
        code, _, out = self.call({"namespace": "otterworks-t2", "request_time": "0.012",
                                  "path": "/api/v1/files/123/versions/0a1b2c3d-0000-4000-8000-00000000abcd/",
                                  "user_agent": "OtterWorksApp/iOS 4.2",
                                  "kubernetes": {"container_name": "controller", "namespace_name": "ingress-nginx"}})
        self.assertEqual(code, 2)
        self.assertEqual(out["cw_group"], "otterworks-t2/ingress-nginx")
        self.assertEqual(out["route"], "/api/v1/files/:id/versions/:id")
        self.assertEqual(out["client"], "ios")
        self.assertAlmostEqual(out["duration_ms"], 12.0)

    def test_foreign_namespaces_and_containers_are_dropped(self):
        for rec in (
            {"route": "/x", "kubernetes": {"container_name": "api-gateway", "namespace_name": "kube-system"}},
            {"namespace": "default", "request_time": 0.1, "path": "/",
             "kubernetes": {"container_name": "controller", "namespace_name": "ingress-nginx"}},
            {"namespace": "otterworks-t1", "path": "/", "kubernetes": {"container_name": "controller", "namespace_name": "ingress-nginx"}},
            {"route": "/x", "kubernetes": {"container_name": "sidecar", "namespace_name": "otterworks-t1"}},
            {"route": "/x"},
        ):
            self.assertEqual(self.call(rec)[0], -1, rec)


if __name__ == "__main__":
    unittest.main()
