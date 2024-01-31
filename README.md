# tensoul-py

Convert MahjongSoul log into tenhou.net/6 format. (Inspired by https://github.com/Equim-chan/tensoul)

## Usage

You need to have an account from CN server, because only accounts from CN server have the ability to login with username and password.

```python
import json
import sys

from tensoul import MajsoulPaipuDownloader


username = "foo@bar.com"
password = "foobar"
record_uuid = "123456-abcdefgh-1234-abcd-1234-12345678abcd"  # taken from majsoul log link: https://game.maj-soul.com/1/?paipu=<this_part>_a12345678

downloader = MajsoulPaipuDownloader()
await downloader.start(username, password)
try:
    logs = await downloader.download(record_uuid)
    json.dump(logs, sys.stdout, ensure_ascii=False)
finally:
    await downloader.close()
```

See example.py also

## Thanks

https://github.com/MahjongRepository/mahjong_soul_api

https://repo.riichi.moe/library.html#resources-majplus
