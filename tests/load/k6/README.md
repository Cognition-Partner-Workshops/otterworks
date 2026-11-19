# OtterWorks k6 suite

See [the load-testing guide](../../../docs/LOAD-TESTING.md) for profiles, SLOs, safety,
cluster execution and measured findings. k6 1.7.1 is pinned in CI and the Job.

```sh
make loadtest-smoke BASE_URL=https://api-t-loadtest.demo.otterworks.app
DURATION=5m make loadtest-peak TARGET=https://api-t-loadtest.demo.otterworks.app
node --test tests/load/k6/tests/*.test.mjs
```

`otterworks.js` is the shared entry point, preserving the original health-only
`READ_ONLY=1` mode and VU profiles. `lib/` contains configuration, auth and
instrumented HTTP helpers; `busy-season.js` adds setup, the weighted journey
and summaries. `k8s/run.sh` packages those
same files into a ConfigMap; it does not require rebuilding an image.
`results/` is ignored and must exist before running k6 directly:

```sh
mkdir -p tests/load/k6/results
BASE_URL=https://api-t-loadtest.demo.otterworks.app PROFILE=smoke k6 run tests/load/k6/otterworks.js
```
