#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 BestCF 拉取最新 Cloudflare 优选域名，写入 EDGE_HOSTS 环境变量。

用法：在 GitHub Actions 的 check.yml 里，vpngate.py 运行之前加一步：
    - name: Fetch latest Cloudflare preferred domains
      run: python fetch_edge_hosts.py

vpngate.py 读取 EDGE_HOSTS 时优先使用环境变量
(os.environ.get("EDGE_HOSTS", ...))，因此无需修改 vpngate.py 本身。
本脚本只用标准库，无需额外依赖。
"""
import os
import re
import urllib.request

# 主数据源：BestCF 站点的纯文本域名池（每行一个域名，可带端口）
# 备用源：同一份数据的 GitHub raw 直链
SOURCES = [
    "https://bestcf.fxxk.dedyn.io/cf_domains.txt",
    "https://raw.githubusercontent.com/cmliu/CF-Pages-BestCF/main/cf_domains.txt",
]

# 每次取前 N 个域名，可通过环境变量 EDGE_HOSTS_MAX 调整
MAX_HOSTS = int(os.environ.get("EDGE_HOSTS_MAX", "50"))
# 没有带端口的域名统一补上 443（vpngate 要求每个地址带 :443）
DEFAULT_PORT = "443"
# 只允许安全的域名字符，防止脏数据污染环境变量
TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]+(:\d+)?$")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse(text: str) -> list:
    hosts, seen = [], set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split()[0].split("#")[0].strip()
        if not TOKEN_RE.match(token):
            continue
        if ":" not in token:
            token = f"{token}:{DEFAULT_PORT}"
        if token not in seen:
            seen.add(token)
            hosts.append(token)
    return hosts


def main() -> None:
    hosts = []
    for url in SOURCES:
        try:
            hosts = parse(fetch(url))
            if hosts:
                print(f"[ok] 从 {url} 获取到 {len(hosts)} 个优选域名")
                break
            print(f"[warn] {url} 返回为空，尝试下一个来源")
        except Exception as exc:  # noqa: BLE001 - 任意失败都走备用源
            print(f"[warn] 拉取 {url} 失败: {exc}")

    if not hosts:
        # 所有来源都失败：不写 GITHUB_ENV，vpngate.py 会回退到代码里的默认域名池
        print("[warn] 所有来源都失败，本次不覆盖 EDGE_HOSTS，沿用原有配置")
        return

    hosts = hosts[:MAX_HOSTS]
    value = ",".join(hosts)
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as f:
            f.write(f"EDGE_HOSTS={value}\n")
        print(f"[ok] 已写入 EDGE_HOSTS，共 {len(hosts)} 个")
    else:
        # 本地调试时直接打印
        print(f"EDGE_HOSTS={value}")


if __name__ == "__main__":
    main()
