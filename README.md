# lokikit

A minimal CLI to set up and run a local Loki+Promtail+Grafana stack.

## Usage

Install with [uv tools](https://docs.astral.sh/uv/guides/tools/):

```sh
uv tools install git+https://github.com/iamgp/lokikit.git
lokikit setup
lokikit start
Access Grafana at http://localhost:3000
Run lokikit clean to remove all files.
Disclaimer:
This project is not affiliated with or endorsed by Grafana Labs. Loki is a trademark of Grafana Labs.
```
