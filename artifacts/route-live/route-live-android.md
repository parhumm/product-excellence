# Live route acceptance: android

| interface | route route-a-live-01 | host-side proxy | app on route A | switch | app on route B | route direct | app off every route | direct reaches no upstream | relay closed |
|---|---|---|---|---|---|---|---|---|---|
| relay | pass | - | - | - | - | - | - | - | - |
| device | - | pass | - | - | - | - | - | - | - |
| app | - | - | pass | - | pass | - | pass | - | - |
| switch | - | - | - | pass | - | pass | - | pass | - |
| cleanup | - | - | - | - | - | - | - | - | pass |

```
{
  "probes": [
    "http://127.0.0.1:61907/exit",
    "http://192.0.2.10/exit"
  ],
  "build": {
    "package": "dev.pex.crashapp",
    "sha256": "7a03591adaeb9f747136dff23f4e4ca99b24c67da49548f3b68e241cb85200cb",
    "version_name": "1.0",
    "version_code": 1,
    "min_sdk": 23,
    "target_sdk": 34,
    "launch_activity": "dev.pex.crashapp.MainActivity",
    "abis": [],
    "size": 12691
  },
  "serial": "emulator-5554",
  "network_restore": [],
  "route_traffic": {
    "1": {
      "accepted": 125,
      "established": 11,
      "bytes": 276,
      "probe_accepted": 2,
      "probe_established": 2,
      "probe_bytes": 13
    },
    "2": {
      "accepted": 206,
      "established": 5,
      "bytes": 277,
      "probe_accepted": 2,
      "probe_established": 2,
      "probe_bytes": 14
    },
    "3": {
      "accepted": 22,
      "established": 20,
      "bytes": 133255,
      "probe_accepted": 1,
      "probe_established": 1,
      "probe_bytes": 10
    }
  },
  "upstream_requests": {
    "route-a-live-01": [
      {
        "at": 1789503247.697252,
        "line": "CONNECT 142.251.155.119:443 HTTP/1.1",
        "authority": "142.251.155.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503247.71825,
        "line": "GET http://www.google.com/gen_204 HTTP/1.1",
        "authority": "http://www.google.com/gen_204",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503248.968724,
        "line": "GET http://connectivitycheck.gstatic.com/generate_204 HTTP/1.1",
        "authority": "http://connectivitycheck.gstatic.com/generate_204",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503249.131309,
        "line": "CONNECT 142.251.155.119:443 HTTP/1.1",
        "authority": "142.251.155.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503249.378966,
        "line": "GET http://play.googleapis.com/generate_204 HTTP/1.1",
        "authority": "http://play.googleapis.com/generate_204",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.5596611,
        "line": "CONNECT 142.251.45.86:443 HTTP/1.1",
        "authority": "142.251.45.86:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.590544,
        "line": "CONNECT 142.250.217.150:443 HTTP/1.1",
        "authority": "142.250.217.150:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.5934641,
        "line": "CONNECT 172.217.115.4:443 HTTP/1.1",
        "authority": "172.217.115.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.59487,
        "line": "CONNECT 142.251.210.54:443 HTTP/1.1",
        "authority": "142.251.210.54:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.5960262,
        "line": "CONNECT 172.217.119.4:443 HTTP/1.1",
        "authority": "172.217.119.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.5963562,
        "line": "CONNECT 142.251.211.118:443 HTTP/1.1",
        "authority": "142.251.211.118:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.598009,
        "line": "CONNECT 172.217.112.4:443 HTTP/1.1",
        "authority": "172.217.112.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.602465,
        "line": "CONNECT 142.250.65.246:443 HTTP/1.1",
        "authority": "142.250.65.246:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.621601,
        "line": "CONNECT 172.217.116.4:443 HTTP/1.1",
        "authority": "172.217.116.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.6216068,
        "line": "CONNECT 142.251.45.214:443 HTTP/1.1",
        "authority": "142.251.45.214:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.6255648,
        "line": "CONNECT 172.217.117.4:443 HTTP/1.1",
        "authority": "172.217.117.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.62557,
        "line": "CONNECT 142.251.111.119:443 HTTP/1.1",
        "authority": "142.251.111.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.627319,
        "line": "CONNECT 172.217.113.4:443 HTTP/1.1",
        "authority": "172.217.113.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.6273332,
        "line": "CONNECT 172.253.122.119:443 HTTP/1.1",
        "authority": "172.253.122.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.629025,
        "line": "CONNECT 172.217.114.4:443 HTTP/1.1",
        "authority": "172.217.114.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.62913,
        "line": "CONNECT 192.179.24.119:443 HTTP/1.1",
        "authority": "192.179.24.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.630028,
        "line": "CONNECT 172.217.118.4:443 HTTP/1.1",
        "authority": "172.217.118.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.630176,
        "line": "CONNECT 142.251.45.182:443 HTTP/1.1",
        "authority": "142.251.45.182:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.632229,
        "line": "CONNECT 142.251.211.182:443 HTTP/1.1",
        "authority": "142.251.211.182:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.634161,
        "line": "CONNECT 142.251.41.182:443 HTTP/1.1",
        "authority": "142.251.41.182:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.6355772,
        "line": "CONNECT 142.251.211.150:443 HTTP/1.1",
        "authority": "142.251.211.150:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.637795,
        "line": "CONNECT 142.250.188.22:443 HTTP/1.1",
        "authority": "142.250.188.22:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.6390889,
        "line": "CONNECT 142.250.72.22:443 HTTP/1.1",
        "authority": "142.250.72.22:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503251.6408498,
        "line": "CONNECT 142.250.65.86:443 HTTP/1.1",
        "authority": "142.250.65.86:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503252.363254,
        "line": "CONNECT 142.251.155.119:443 HTTP/1.1",
        "authority": "142.251.155.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503252.5039968,
        "line": "GET http://connectivitycheck.gstatic.com/generate_204 HTTP/1.1",
        "authority": "http://connectivitycheck.gstatic.com/generate_204",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503252.711551,
        "line": "GET http://play.googleapis.com/generate_204 HTTP/1.1",
        "authority": "http://play.googleapis.com/generate_204",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503253.804085,
        "line": "CONNECT 192.179.18.188:5228 HTTP/1.1",
        "authority": "192.179.18.188:5228",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503254.907169,
        "line": "CONNECT 192.178.234.188:443 HTTP/1.1",
        "authority": "192.178.234.188:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503255.319346,
        "line": "CONNECT 142.250.65.232:443 HTTP/1.1",
        "authority": "142.250.65.232:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503255.8659341,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503255.867038,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503255.8685389,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.083224,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.085205,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.0866182,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.0877812,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.0889769,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.090224,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.091137,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.092576,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.0935838,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.095196,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.0969431,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.0980558,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.099421,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.100851,
        "line": "CONNECT 142.250.217.130:443 HTTP/1.1",
        "authority": "142.250.217.130:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.108202,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.1128151,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503256.117913,
        "line": "CONNECT 142.251.45.198:443 HTTP/1.1",
        "authority": "142.251.45.198:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.372726,
        "line": "CONNECT 142.251.152.119:443 HTTP/1.1",
        "authority": "142.251.152.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.374283,
        "line": "GET http://connectivitycheck.gstatic.com/generate_204 HTTP/1.1",
        "authority": "http://connectivitycheck.gstatic.com/generate_204",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.620878,
        "line": "GET http://play.googleapis.com/generate_204 HTTP/1.1",
        "authority": "http://play.googleapis.com/generate_204",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.852088,
        "line": "CONNECT 172.217.113.4:443 HTTP/1.1",
        "authority": "172.217.113.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.8597188,
        "line": "CONNECT 172.217.114.4:443 HTTP/1.1",
        "authority": "172.217.114.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.8610282,
        "line": "CONNECT 172.217.118.4:443 HTTP/1.1",
        "authority": "172.217.118.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.862537,
        "line": "CONNECT 172.217.115.4:443 HTTP/1.1",
        "authority": "172.217.115.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.8634691,
        "line": "CONNECT 172.217.119.4:443 HTTP/1.1",
        "authority": "172.217.119.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.86524,
        "line": "CONNECT 172.217.112.4:443 HTTP/1.1",
        "authority": "172.217.112.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.866464,
        "line": "CONNECT 172.217.116.4:443 HTTP/1.1",
        "authority": "172.217.116.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503257.867624,
        "line": "CONNECT 172.217.117.4:443 HTTP/1.1",
        "authority": "172.217.117.4:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.269591,
        "line": "CONNECT 142.251.151.119:443 HTTP/1.1",
        "authority": "142.251.151.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.2731829,
        "line": "CONNECT 142.251.157.119:443 HTTP/1.1",
        "authority": "142.251.157.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.274667,
        "line": "CONNECT 142.251.156.119:443 HTTP/1.1",
        "authority": "142.251.156.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.275769,
        "line": "CONNECT 142.251.155.119:443 HTTP/1.1",
        "authority": "142.251.155.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.276843,
        "line": "CONNECT 142.251.150.119:443 HTTP/1.1",
        "authority": "142.251.150.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.281653,
        "line": "CONNECT 142.251.152.119:443 HTTP/1.1",
        "authority": "142.251.152.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.282586,
        "line": "CONNECT 142.251.154.119:443 HTTP/1.1",
        "authority": "142.251.154.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.283842,
        "line": "CONNECT 142.251.153.119:443 HTTP/1.1",
        "authority": "142.251.153.119:443",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503258.947432,
    
```
