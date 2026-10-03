# -*- coding: utf-8 -*-
"""
publish_to_github.py —— 把本目录一键发布到 GitHub（用官方 REST API，本机不需要安装 git）

使用步骤：
  1. 在 GitHub 生成 Personal Access Token（classic，勾选 repo 权限即可）：
         https://github.com/settings/tokens
     （Fine-grained token 也可以：给这个仓库 Contents: Read and write 权限）

  2. 在【你自己的终端】里设置环境变量（不要把 token 发给任何人、不要发到聊天里）：
         PowerShell:   $env:GH_TOKEN = "ghp_你的token"
         CMD:          set GH_TOKEN=ghp_你的token

  3. 在本目录运行：
         python publish_to_github.py 仓库名                     # 公开仓库
         python publish_to_github.py 仓库名 --private           # 私有仓库
         python publish_to_github.py 仓库名 --desc "描述"       # 自定义描述
         python publish_to_github.py 仓库名 --dry-run           # 只看会上传哪些文件

脚本会自动：读取你的用户名 -> 创建仓库（已存在则复用）-> 上传目录下所有文件。
"""

import argparse
import base64
import getpass
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
SKIP_DIRS = {".git", "__pycache__", ".idea", ".vscode", "dist", "build"}
SKIP_EXT = {".pyc", ".pyo", ".pyd"}

HERE = Path(__file__).resolve().parent


def api(method, path, token, payload=None):
    """调用 GitHub REST API，返回 (状态码, 响应dict 或 None)"""
    url = API + path if path.startswith("/") else API + "/" + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            return e.code, (json.loads(body) if body else None)
        except Exception:
            return e.code, None


def collect_files():
    """收集要上传的文件（相对路径列表）"""
    files = []
    for root, dirs, names in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".git")]
        for n in names:
            if os.path.splitext(n)[1].lower() in SKIP_EXT:
                continue
            p = Path(root) / n
            rel = p.relative_to(HERE).as_posix()
            if rel != Path(__file__).name:          # 不上传本脚本自身
                files.append((rel, p))
    return sorted(files)


def main():
    ap = argparse.ArgumentParser(description="Publish this folder to GitHub (no git needed)")
    ap.add_argument("repo", help="仓库名，例如 sound-explorer")
    ap.add_argument("--private", action="store_true", help="创建为私有仓库")
    ap.add_argument("--desc", default="", help="仓库描述")
    ap.add_argument("--dry-run", action="store_true", help="只列出将上传的文件，不做任何操作")
    ap.add_argument("--msg", default="Initial release", help="提交说明")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("未检测到环境变量 GH_TOKEN。")
        token = getpass.getpass("也可以直接粘贴 token（输入不会回显）：").strip()
    if not token:
        sys.exit("没有 token，退出。")

    if args.dry_run:
        print("将上传以下文件：")
        for rel, p in collect_files():
            print("  %-40s %6.1f KB" % (rel, p.stat().st_size / 1024))
        return

    # 1) 用户名
    code, me = api("GET", "/user", token)
    if code != 200:
        sys.exit("获取账号信息失败（HTTP %s）：%s\n请检查 token 是否有效、是否勾选了 repo 权限。"
                 % (code, (me or {}).get("message", "")))
    login = me["login"]
    print("账号：%s" % login)

    # 2) 仓库（存在则复用，不存在则创建）
    full = "%s/%s" % (login, args.repo)
    code, repo = api("GET", "/repos/" + full, token)
    if code == 200:
        print("仓库已存在，直接复用：%s" % repo["html_url"])
    else:
        code, repo = api("POST", "/user/repos", token, {
            "name": args.repo,
            "private": args.private,
            "description": args.desc or ("Sound Explorer / 音律探索器 — piano frequencies & pitch detection"),
            "auto_init": False,
        })
        if code not in (201, 202):
            msg = (repo or {}).get("message", "")
            sys.exit("创建仓库失败（HTTP %s）：%s" % (code, msg))
        print("仓库已创建：%s" % repo["html_url"])

    # 3) 上传文件
    files = collect_files()
    print("开始上传 %d 个文件..." % len(files))
    for rel, p in files:
        content = base64.b64encode(p.read_bytes()).decode("ascii")
        code, old = api("GET", "/repos/%s/contents/%s" % (full, urllib.parse.quote(rel)), token)
        sha = old["sha"] if code == 200 else None
        code, resp = api("PUT", "/repos/%s/contents/%s" % (full, urllib.parse.quote(rel)), token, {
            "message": args.msg,
            "content": content,
            **({"sha": sha} if sha else {}),
        })
        if code in (200, 201):
            print("  [OK] %s" % rel)
        else:
            print("  [失败 HTTP %s] %s : %s" % (code, rel, (resp or {}).get("message", "")))

    print("\n完成！仓库地址：%s" % repo["html_url"])


if __name__ == "__main__":
    main()
