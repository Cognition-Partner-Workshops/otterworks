import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import replay


CONTEXT = "kind-aks-source"
IMAGE = f"{replay.REPOSITORY}:baseline-test"
DIGEST = f"sha256:{'a' * 64}"


def context_config(server, **options):
    return json.dumps({
        "current-context": CONTEXT,
        "clusters": [{"name": CONTEXT, "cluster": {"server": server, **options}}],
    })


def pod(uid, *, ready=True, terminating=False, digest=DIGEST):
    return {
        "metadata": {"name": f"sample-{uid}", "uid": uid,
                     **({"deletionTimestamp": "2026-11-28T00:00:00Z"} if terminating else {})},
        "spec": {"nodeName": "aks-source-control-plane"},
        "status": {"phase": "Running", "containerStatuses": [
            {"name": replay.APP, "ready": ready, "image": IMAGE, "imageID": digest}
        ]},
    }


class IsolationTest(unittest.TestCase):
    def test_inherited_overrides_are_not_forwarded_to_cluster_commands(self):
        overrides = dict.fromkeys((
            "HELM_KUBEAPISERVER", "HELM_KUBETOKEN", "HELM_KUBECAFILE", "HELM_KUBECONTEXT",
            "HELM_KUBEINSECURE_SKIP_TLS_VERIFY", "HELM_NAMESPACE", "HELM_DRIVER", "KUBECONFIG",
            "KUBERNETES_SERVICE_HOST", "HTTPS_PROXY", "https_proxy", "KIND_EXPERIMENTAL_PROVIDER",
        ), "ignored")
        with patch.dict(os.environ, {"PATH": "/bin", **overrides}, clear=True):
            env = replay.local_env()
        self.assertEqual(env, {"PATH": "/bin", "KIND_EXPERIMENTAL_PROVIDER": "docker"})
        result = {"identity": replay.identity("aks-source"), "checks": {"setup": {}}}
        with patch.object(replay, "command", side_effect=[
                "", context_config("https://cluster.invalid:6443")]) as command:
            replay.run_cluster("aks-source", result, {}, env, lambda: None,
                               Path("/isolated/image.tar"), "baseline-test", DIGEST)
        self.assertEqual(command.call_count, 2)
        self.assertEqual(command.call_args.args[:5],
                         ("kubectl", "--kubeconfig", Path("/isolated/aks-source.kubeconfig"),
                          "--context", CONTEXT))
        self.assertEqual(command.call_args.kwargs["env"], env)
        self.assertIn("Refusing non-local kind endpoint", result["checks"]["setup"]["error"])

    def test_local_endpoint_must_match_the_kind_container_binding(self):
        for binding, accepted in (("127.0.0.1:32123\n", True), ("127.0.0.1:32124\n", False)):
            with self.subTest(binding=binding), patch.object(replay, "command", side_effect=[
                    context_config("https://127.0.0.1:32123"), binding]):
                if accepted:
                    replay.verify_local_context(("kubectl",), CONTEXT, "aks-source", {})
                else:
                    with self.assertRaisesRegex(RuntimeError, "not the docker port"):
                        replay.verify_local_context(("kubectl",), CONTEXT, "aks-source", {})

    def test_local_endpoint_with_an_explicit_proxy_is_rejected(self):
        with patch.object(replay, "command", return_value=context_config(
                "https://127.0.0.1:32123", **{"proxy-url": "https://proxy.invalid"})):
            with self.assertRaisesRegex(RuntimeError, "Refusing non-local kind endpoint"):
                replay.verify_local_context(("kubectl",), CONTEXT, "aks-source", {})


class ReadyPodTest(unittest.TestCase):
    def test_restart_waits_past_old_absent_terminating_and_unready_pods(self):
        snapshots = [[pod("old")], [], [pod("terminating", terminating=True), pod("new", ready=False)],
                     [pod("new")]]
        with patch.object(replay, "command", side_effect=(
                json.dumps({"items": items}) for items in snapshots)) as command, \
                patch.object(replay.time, "sleep"):
            selected = replay.ready_pod(("kubectl",), {}, IMAGE, DIGEST, old_uid="old")
        self.assertEqual(selected["uid"], "new")
        self.assertEqual(selected["pod"], "sample-new")
        self.assertEqual(selected["digest"], DIGEST)
        self.assertEqual(command.call_count, len(snapshots))
        self.assertTrue(all(call.args[1:3] == ("get", "pods") for call in command.call_args_list))

    def test_restart_times_out_instead_of_accepting_old_uid(self):
        with patch.object(replay, "command", return_value=json.dumps({"items": [pod("old")]})), \
                patch.object(replay.time, "monotonic", side_effect=[0, 0, 1, 2]), \
                patch.object(replay.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "replacing pod UID old"):
                replay.ready_pod(("kubectl",), {}, IMAGE, DIGEST, old_uid="old", timeout=2)

    def test_matching_tag_does_not_accept_another_image_digest(self):
        with self.assertRaisesRegex(RuntimeError, "Unexpected running pod image"):
            replay.select_ready_pod({"items": [pod("new", digest=f"sha256:{'b' * 64}")]},
                                    IMAGE, DIGEST, None)

    def test_archive_digest_uses_config_bytes_and_checks_tag(self):
        config = b'{"config":{"User":"10001"}}'
        manifest = json.dumps([{"Config": "config.json", "RepoTags": [IMAGE]}]).encode()
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "image.tar"
            with tarfile.open(archive, "w") as saved:
                for name, data in (("manifest.json", manifest), ("config.json", config)):
                    entry = tarfile.TarInfo(name)
                    entry.size = len(data)
                    saved.addfile(entry, io.BytesIO(data))
            self.assertEqual(replay.archive_digest(archive, IMAGE),
                             f"sha256:{hashlib.sha256(config).hexdigest()}")
            with self.assertRaisesRegex(RuntimeError, "unique replay image"):
                replay.archive_digest(archive, IMAGE + "-old")


if __name__ == "__main__":
    unittest.main()
