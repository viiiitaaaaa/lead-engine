"""Выкладка сайта в Яндекс Облако (Object Storage) — сайт открывается из России без VPN.
Запуск: python site/deploy_yc.py   (сперва собирает сайт так же, как deploy_cf.ps1, потом заливает папку dist в бакет)
Ключи НЕ в коде и НЕ в git: файл C:\\Users\\User\\tools\\site-dist\\yc_keys.env с тремя строками
    YC_KEY_ID=...      YC_SECRET=...      YC_BUCKET=имя-бакета-без-точек
"""
import mimetypes
import os
import subprocess
import sys

import boto3

SITE = os.path.dirname(os.path.abspath(__file__))
TOOLS = r"C:\Users\User\tools\site-dist"
DIST = os.path.join(TOOLS, "dist")
KEYS = os.path.join(TOOLS, "yc_keys.env")


def load_keys():
    if not os.path.exists(KEYS):
        sys.exit(f"Нет файла с ключами: {KEYS}")
    d = {}
    for line in open(KEYS, encoding="utf-8"):
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            d[k.strip()] = v.strip()
    for k in ("YC_KEY_ID", "YC_SECRET", "YC_BUCKET"):
        if not d.get(k):
            sys.exit(f"В {KEYS} не хватает {k}")
    return d


def build():
    # та же сборка, что в deploy_cf.ps1: страницы -> чистая версия в dist
    subprocess.run([sys.executable, os.path.join(SITE, "build.py")], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["node", os.path.join(SITE, "build_dist.js"), SITE, DIST], check=True, cwd=TOOLS)


def main():
    k = load_keys()
    if "--no-build" not in sys.argv:
        build()
    s3 = boto3.client("s3", endpoint_url="https://storage.yandexcloud.net", region_name="ru-central1",
                      aws_access_key_id=k["YC_KEY_ID"], aws_secret_access_key=k["YC_SECRET"])
    bucket = k["YC_BUCKET"]
    n = 0
    for root, _, files in os.walk(DIST):
        for f in files:
            path = os.path.join(root, f)
            key = os.path.relpath(path, DIST).replace("\\", "/")
            ctype = mimetypes.guess_type(f)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            s3.upload_file(path, bucket, key, ExtraArgs={"ContentType": ctype, "ACL": "public-read"})
            n += 1
    s3.put_bucket_website(Bucket=bucket, WebsiteConfiguration={
        "IndexDocument": {"Suffix": "index.html"}, "ErrorDocument": {"Key": "index.html"}})
    print(f"Залито файлов: {n}")
    print(f"Адрес: http://{bucket}.website.yandexcloud.net")


main()
# Что делает скрипт целиком: собирает сайт, заливает все файлы в твой бакет Яндекс Облака, включает режим «сайт» (главная — index.html).
