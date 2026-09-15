# Android transport gate

| interface | host-side proxy | route tcp/80 | route tcp/443 | route tcp/9101 | shape delay | shape bandwidth | route switch |
|---|---|---|---|---|---|---|---|
| device | pass | - | - | - | - | - | - |
| wifi | - | pass | pass | pass | absent | absent | - |
| cellular | - | pass | pass | pass | pass | pass | - |
| switch | - | - | - | - | - | - | pass |

```
{
  "emulator": "Android emulator version 36.6.11.0 (build_id 15507667) (CL:N/A)",
  "serial": "emulator-5554",
  "launch_args": "/opt/homebrew/share/android-commandlinetools/emulator/emulator -avd pex-test -http-proxy http://127.0.0.1:55517 -no-snapshot -no-audio -gpu auto -verbose -no-window",
  "api": "34",
  "abi": "arm64-v8a",
  "network_before": {
    "console": "Current network status:\n  download speed:          0 bits/s (0.0 KB/s)\n  upload speed:            0 bits/s (0.0 KB/s)\n  minimum latency:  0 ms\n  maximum latency:  0 ms\nOK",
    "wifi": "0",
    "data": "1"
  },
  "guest_http_proxy": "null",
  "wifi_active_route": "101",
  "cellular_active_route": "102",
  "proxy_requests": [
    {
      "at": 1789474688.091512,
      "line": "CONNECT 172.217.114.4:443 HTTP/1.1",
      "authority": "172.217.114.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.091516,
      "line": "CONNECT [2001:4860:4845:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4845:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.0940092,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.095026,
      "line": "CONNECT 172.217.115.4:443 HTTP/1.1",
      "authority": "172.217.115.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.098444,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.09847,
      "line": "CONNECT 172.217.119.4:443 HTTP/1.1",
      "authority": "172.217.119.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.098784,
      "line": "CONNECT [2001:4860:4843:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4843:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.0993311,
      "line": "CONNECT [2001:4860:4842:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4842:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1004329,
      "line": "CONNECT [2001:4860:4845:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4845:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.100687,
      "line": "CONNECT 172.217.115.4:443 HTTP/1.1",
      "authority": "172.217.115.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.101726,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1138291,
      "line": "CONNECT [2001:4860:4846:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4846:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.113847,
      "line": "CONNECT 172.217.119.4:443 HTTP/1.1",
      "authority": "172.217.119.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.114079,
      "line": "CONNECT [2001:4860:4846:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4846:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.11628,
      "line": "CONNECT [2001:4860:4840:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4840:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1162932,
      "line": "CONNECT 172.217.117.4:443 HTTP/1.1",
      "authority": "172.217.117.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.121181,
      "line": "CONNECT [2001:4860:4843:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4843:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.121537,
      "line": "CONNECT 172.217.117.4:443 HTTP/1.1",
      "authority": "172.217.117.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.122473,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.122782,
      "line": "CONNECT [2001:4860:4845:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4845:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1232262,
      "line": "CONNECT [2001:4860:4842:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4842:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.127817,
      "line": "CONNECT [2001:4860:4845:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4845:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.128281,
      "line": "CONNECT [2001:4860:4846:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4846:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.128509,
      "line": "CONNECT [2001:4860:4842:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4842:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.129687,
      "line": "CONNECT [2001:4860:4843:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4843:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.130124,
      "line": "CONNECT [2001:4860:4843:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4843:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1320908,
      "line": "CONNECT [2001:4860:4840:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4840:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.132343,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.134976,
      "line": "CONNECT [2001:4860:4840:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4840:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.13499,
      "line": "CONNECT [2001:4860:4840:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4840:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1366642,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.139105,
      "line": "CONNECT [2001:4860:4845:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4845:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.139123,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1413782,
      "line": "CONNECT [2001:4860:4846:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4846:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.142022,
      "line": "CONNECT [2001:4860:4846:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4846:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1425312,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.143317,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.14489,
      "line": "CONNECT [2001:4860:4843:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4843:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.149878,
      "line": "CONNECT [2001:4860:4843:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4843:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.15092,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.151838,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.151925,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.152123,
      "line": "CONNECT [2001:4860:4840:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4840:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.153752,
      "line": "CONNECT [2001:4860:4840:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4840:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.156422,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.157714,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1606688,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.160807,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.161685,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.165993,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.166322,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.166668,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.1709728,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474688.262002,
      "line": "CONNECT 192.0.2.10:9101 HTTP/1.1",
      "authority": "192.0.2.10:9101",
      "fixture": true,
      "served": "tunnelled",
      "verbs_seen": "f7451c4eaa7f:GET",
      "generation": 1,
      "tag": "A"
    },
    {
      "at": 1789474688.738466,
      "line": "CONNECT 192.0.2.10:9101 HTTP/1.1",
      "authority": "192.0.2.10:9101",
      "fixture": true,
      "served": "tunnelled",
      "verbs_seen": "317f12f181d1:GET",
      "generation": 1,
      "tag": "A"
    },
    {
      "at": 1789474689.120942,
      "line": "CONNECT [2001:4860:4846:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4846:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.122206,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1240551,
      "line": "CONNECT [2001:4860:4842:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4842:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.125087,
      "line": "CONNECT [2001:4860:4843:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4843:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.125901,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.126716,
      "line": "CONNECT [2001:4860:4840:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4840:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1277251,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.128685,
      "line": "CONNECT [2001:4860:4845:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4845:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1296608,
      "line": "CONNECT 172.217.115.4:443 HTTP/1.1",
      "authority": "172.217.115.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.130753,
      "line": "CONNECT 172.217.117.4:443 HTTP/1.1",
      "authority": "172.217.117.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1323001,
      "line": "CONNECT 172.217.112.4:443 HTTP/1.1",
      "authority": "172.217.112.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1333609,
      "line": "CONNECT 172.217.114.4:443 HTTP/1.1",
      "authority": "172.217.114.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.134155,
      "line": "CONNECT 172.217.113.4:443 HTTP/1.1",
      "authority": "172.217.113.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.135159,
      "line": "CONNECT 172.217.118.4:443 HTTP/1.1",
      "authority": "172.217.118.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.135954,
      "line": "CONNECT 172.217.116.4:443 HTTP/1.1",
      "authority": "172.217.116.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1368608,
      "line": "CONNECT 172.217.119.4:443 HTTP/1.1",
      "authority": "172.217.119.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.144045,
      "line": "CONNECT [2001:4860:4846:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4846:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1453729,
      "line": "CONNECT [2001:4860:4841:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4841:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.146361,
      "line": "CONNECT [2001:4860:4842:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4842:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.147388,
      "line": "CONNECT [2001:4860:4843:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4843:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.148512,
      "line": "CONNECT [2001:4860:4844:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4844:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1485188,
      "line": "CONNECT 172.217.115.4:443 HTTP/1.1",
      "authority": "172.217.115.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.149636,
      "line": "CONNECT [2001:4860:4840:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4840:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1508312,
      "line": "CONNECT [2001:4860:4847:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4847:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1512032,
      "line": "CONNECT 172.217.117.4:443 HTTP/1.1",
      "authority": "172.217.117.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1517818,
      "line": "CONNECT [2001:4860:4845:400::]:443 HTTP/1.1",
      "authority": "[2001:4860:4845:400::]:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.152382,
      "line": "CONNECT 172.217.112.4:443 HTTP/1.1",
      "authority": "172.217.112.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.153727,
      "line": "CONNECT 172.217.115.4:443 HTTP/1.1",
      "authority": "172.217.115.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.1543949,
      "line": "CONNECT 172.217.114.4:443 HTTP/1.1",
      "authority": "172.217.114.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.154966,
      "line": "CONNECT 172.217.117.4:443 HTTP/1.1",
      "authority": "172.217.117.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""
    },
    {
      "at": 1789474689.156062,
      "line": "CONNECT 172.217.112.4:443 HTTP/1.1",
      "authority": "172.217.112.4:443",
      "fixture": false,
      "served": "refused",
      "verbs_seen": ""

```
