import asyncio
import json
import os
from argparse import ArgumentParser

from tensoul import MajsoulPaipuDownloader


async def download(username: str, password: str, record_uuid: str):
    async with MajsoulPaipuDownloader() as downloader:
        await downloader.login(username, password)
        return await downloader.download(record_uuid)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("record", help="Your record UUID for load.")
    parser.add_argument("-u", "--username", help="Your account name.", dest="username")
    parser.add_argument("-p", "--password", help="Your account password.", dest="password")

    args = parser.parse_args()

    logs = asyncio.run(download(args.username, args.password, args.record))

    os.makedirs("records", exist_ok=True)
    with open(f"records/{args.record}.json", "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False)
