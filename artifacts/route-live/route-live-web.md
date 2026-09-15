# Live route acceptance: web

| interface | route route-a-live-01 | page on route A | switch | page on route B | credentials upstream only | route with speed | long-lived tunnel | switch disconnects | route direct | direct reaches no upstream | relay closed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| relay | pass | - | - | - | - | - | pass | pass | pass | pass | - |
| chromium | - | pass | pass | pass | pass | pass | - | - | - | - | - |
| firefox | - | pass | pass | pass | pass | - | - | - | - | - | - |
| webkit | - | pass | pass | pass | pass | - | - | - | - | - | - |
| cleanup | - | - | - | - | - | - | - | - | - | - | pass |

```
{
  "probes": [
    "http://127.0.0.1:63011/exit",
    "http://192.0.2.10/exit"
  ],
  "probe_substitution": "The two public exit-IP echoes are replaced by controlled ones. What is measured is which upstream carried the request, not internet reachability.",
  "relay": "http://127.0.0.1:63014",
  "route_traffic": {
    "1": {
      "accepted": 3,
      "established": 3,
      "bytes": 36,
      "probe_accepted": 2,
      "probe_established": 2,
      "probe_bytes": 13
    },
    "2": {
      "accepted": 4,
      "established": 4,
      "bytes": 32805,
      "probe_accepted": 2,
      "probe_established": 2,
      "probe_bytes": 14
    },
    "3": {
      "accepted": 5,
      "established": 5,
      "bytes": 32826,
      "probe_accepted": 2,
      "probe_established": 2,
      "probe_bytes": 13
    },
    "4": {
      "accepted": 3,
      "established": 3,
      "bytes": 37,
      "probe_accepted": 2,
      "probe_established": 2,
      "probe_bytes": 14
    },
    "5": {
      "accepted": 2,
      "established": 1,
      "bytes": 23,
      "probe_accepted": 0,
      "probe_established": 0,
      "probe_bytes": 0
    },
    "6": {
      "accepted": 4,
      "established": 4,
      "bytes": 85,
      "probe_accepted": 2,
      "probe_established": 2,
      "probe_bytes": 14
    },
    "7": {
      "accepted": 2,
      "established": 1,
      "bytes": 10,
      "probe_accepted": 1,
      "probe_established": 1,
      "probe_bytes": 10
    }
  },
  "upstream_requests": {
    "route-a-live-01": [
      {
        "at": 1789503306.794163,
        "line": "GET http://127.0.0.1:63011/exit HTTP/1.1",
        "authority": "http://127.0.0.1:63011/exit",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503306.802022,
        "line": "GET http://192.0.2.10/exit HTTP/1.1",
        "authority": "http://192.0.2.10/exit",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "exit:GET",
        "auth": false,
        "generation": 1,
        "tag": "A"
      },
      {
        "at": 1789503307.3739378,
        "line": "GET http://192.0.2.10/page/106b3efb7abb HTTP/1.1",
        "authority": "http://192.0.2.10/page/106b3efb7abb",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "106b3efb7abb:GET",
        "auth": false,
        "generation": 1,
        "tag": "A"
      },
      {
        "at": 1789503307.4513001,
        "line": "GET http://127.0.0.1:63011/exit HTTP/1.1",
        "authority": "http://127.0.0.1:63011/exit",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": false
      },
      {
        "at": 1789503307.4590762,
        "line": "GET http://192.0.2.10/exit HTTP/1.1",
        "authority": "http://192.0.2.10/exit",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "exit:GET",
        "auth": false,
        "generation": 1,
        "tag": "A"
      },
      {
        "at": 1789503307.463455,
        "line": "GET http://192.0.2.10/bytes/32768 HTTP/1.1",
        "authority": "http://192.0.2.10/bytes/32768",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "32768:GET",
        "auth": false,
        "generation": 1,
        "tag": "A"
      },
      {
        "at": 1789503310.0728478,
        "line": "GET http://192.0.2.10/page/ea506bf28c2a HTTP/1.1",
        "authority": "http://192.0.2.10/page/ea506bf28c2a",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "ea506bf28c2a:GET",
        "auth": false,
        "generation": 1,
        "tag": "A"
      },
      {
        "at": 1789503310.147376,
        "line": "GET http://192.0.2.10/favicon.ico HTTP/1.1",
        "authority": "http://192.0.2.10/favicon.ico",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "favicon.ico:GET",
        "auth": false,
        "generation": 1,
        "tag": "A"
      },
      {
        "at": 1789503311.329087,
        "line": "GET http://192.0.2.10/page/b7fc3578eca6 HTTP/1.1",
        "authority": "http://192.0.2.10/page/b7fc3578eca6",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "b7fc3578eca6:GET",
        "auth": false,
        "generation": 1,
        "tag": "A"
      }
    ],
    "route-b-live-02": [
      {
        "at": 1789503307.417225,
        "line": "GET http://127.0.0.1:63011/exit HTTP/1.1",
        "authority": "http://127.0.0.1:63011/exit",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": true
      },
      {
        "at": 1789503307.424937,
        "line": "GET http://192.0.2.10/exit HTTP/1.1",
        "authority": "http://192.0.2.10/exit",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "exit:GET",
        "auth": true,
        "generation": 1,
        "tag": "B"
      },
      {
        "at": 1789503307.427443,
        "line": "GET http://192.0.2.10/page/9ee0c312c926 HTTP/1.1",
        "authority": "http://192.0.2.10/page/9ee0c312c926",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "9ee0c312c926:GET",
        "auth": true,
        "generation": 1,
        "tag": "B"
      },
      {
        "at": 1789503307.4399738,
        "line": "GET http://192.0.2.10/bytes/32768 HTTP/1.1",
        "authority": "http://192.0.2.10/bytes/32768",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "32768:GET",
        "auth": true,
        "generation": 1,
        "tag": "B"
      },
      {
        "at": 1789503310.165971,
        "line": "GET http://127.0.0.1:63011/exit HTTP/1.1",
        "authority": "http://127.0.0.1:63011/exit",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": true
      },
      {
        "at": 1789503310.175979,
        "line": "GET http://192.0.2.10/exit HTTP/1.1",
        "authority": "http://192.0.2.10/exit",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "exit:GET",
        "auth": true,
        "generation": 1,
        "tag": "B"
      },
      {
        "at": 1789503310.194894,
        "line": "GET http://192.0.2.10/page/0ef048cb20f6 HTTP/1.1",
        "authority": "http://192.0.2.10/page/0ef048cb20f6",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "0ef048cb20f6:GET",
        "auth": true,
        "generation": 1,
        "tag": "B"
      },
      {
        "at": 1789503311.5197382,
        "line": "GET http://127.0.0.1:63011/exit HTTP/1.1",
        "authority": "http://127.0.0.1:63011/exit",
        "fixture": false,
        "served": "refused",
        "verbs_seen": "",
        "auth": true
      },
      {
        "at": 1789503311.527242,
        "line": "GET http://192.0.2.10/exit HTTP/1.1",
        "authority": "http://192.0.2.10/exit",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "exit:GET",
        "auth": true,
        "generation": 1,
        "tag": "B"
      },
      {
        "at": 1789503311.655968,
        "line": "GET http://192.0.2.10/page/04d96fd74e31 HTTP/1.1",
        "authority": "http://192.0.2.10/page/04d96fd74e31",
        "fixture": true,
        "served": "answered",
        "verbs_seen": "04d96fd74e31:GET",
        "auth": true,
        "generation": 1,
        "tag": "B"
      },
      {
        "at": 1789503311.8111959,
        "line": "CONNECT 192.0.2.10:9101 HTTP/1.1",
        "authority": "192.0.2.10:9101",
        "fixture": true,
        "served": "tunnelled",
        "verbs_seen": "9101:CONNECT 14cd50ad7351:HOLD",
        "auth": true,
        "generation": 1,
        "tag": "B"
      }
    ]
  }
}
```
