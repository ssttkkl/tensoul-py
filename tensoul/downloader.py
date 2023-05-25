import hashlib
import hmac
import random
import uuid
from datetime import datetime

import aiohttp
import ms.protocol_pb2 as pb
from ms.base import MSRPCChannel
from ms.rpc import Lobby

from .cfg import cfg
from .constants import RUNES, JPNAME
from .parser import MajsoulPaipuParser


class MajsoulLoginError(BaseException):
    ...


class MajsoulDownloadError(BaseException):
    def __init__(self, code: int):
        self.code = code


class MajsoulPaipuDownloader:
    MS_HOST = "https://game.maj-soul.com"

    async def start(self):
        await self._connect()

    async def close(self):
        if self.channel:
            await self.channel.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _connect(self):
        async with aiohttp.ClientSession() as session:
            async with session.get("{}/1/version.json".format(self.MS_HOST)) as res:
                version_res = await res.json()
                self.version = version_res["version"]
                self.version_to_force = self.version.replace(".w", "")

            async with session.get("{}/1/v{}/config.json".format(self.MS_HOST, self.version)) as res:
                config = await res.json()

                url = config["ip"][0]["region_urls"][1]["url"]

            async with session.get(url + "?service=ws-gateway&protocol=ws&ssl=true") as res:
                servers = await res.json()

                servers = servers["servers"]
                server = random.choice(servers)
                self.endpoint = "wss://{}/gateway".format(server)

        self.channel = MSRPCChannel(self.endpoint)
        self.lobby = Lobby(self.channel)

        await self.channel.connect(self.MS_HOST)

    async def login(self, username, password):
        uuid_key = str(uuid.uuid1())

        req = pb.ReqLogin()
        req.account = username
        req.password = hmac.new(b"lailai", password.encode(), hashlib.sha256).hexdigest()
        req.device.is_browser = True
        req.random_key = uuid_key
        req.gen_access_token = True
        req.client_version_string = f"web-{self.version_to_force}"
        req.currency_platforms.append(2)

        res = await self.lobby.login(req)
        token = res.access_token
        if not token:
            raise MajsoulLoginError(res)

        self.token = token

    async def download(self, record_uuid: str):
        req = pb.ReqGameRecord()
        req.game_uuid = record_uuid
        req.client_version_string = f'web-{self.version_to_force}'
        res = await self.lobby.fetch_game_record(req)

        if res.error.code:
            raise MajsoulDownloadError(code=res.error.code)

        return self._handle_game_record(res)

    def _handle_game_record(self, record):
        res = {}
        ruledisp = ""
        lobby = ""  # usually 0, is the custom lobby number
        nplayers = len(record.head.result.players)
        nakas = nplayers - 1  # default
        tsumoloss_off = False

        res["ver"] = "2.3"  # mlog version number
        res["ref"] = record.head.uuid  # game id - copy and paste into "other" on the log page to view

        # PF4 is yonma, PF3 is sanma
        res["ratingc"] = f"PF{nplayers}"

        # rule display
        if nplayers == 3:
            ruledisp += RUNES["sanma"][JPNAME]
        if record.head.config.meta.mode_id:  # ranked or casual
            ruledisp += cfg["desktop"]["matchmode"]["map_"][str(record.head.config.meta.mode_id)]["room_name_jp"]
        elif record.head.config.meta.room_id:  # friendly
            lobby = f": {record.head.config.meta.room_id}"  # can set room number as lobby number
            ruledisp += RUNES["friendly"][JPNAME]  # "Friendly"
            nakas = record.head.config.mode.detail_rule.dora_count
            tsumoloss_off = nplayers == 3 and not record.head.config.mode.detail_rule.have_zimosun
        elif record.head.config.meta.contest_uid:  # tourney
            lobby = f": {record.head.config.meta.contest_uid}"
            ruledisp += RUNES["tournament"][JPNAME]  # "Tournament"
            nakas = record.head.config.mode.detail_rule.dora_count
            tsumoloss_off = nplayers == 3 and not record.head.config.mode.detail_rule.have_zimosun

        if record.head.config.mode.mode == 1:
            ruledisp += RUNES["tonpuu"][JPNAME]  # " East"
        elif record.head.config.mode.mode == 2:
            ruledisp += RUNES["hanchan"][JPNAME]

        if record.head.config.meta.mode_id == 0 and record.head.config.mode.detail_rule.dora_count == 0:
            res["rule"] = {"disp": ruledisp, "aka53": 0, "aka52": 0, "aka51": 0}
        else:
            res["rule"] = {"disp": ruledisp, "aka53": 1, "aka52": 2 if nakas == 4 else 1,
                           "aka51": 1 if nplayers == 4 else 0}

        # tenhou custom lobby - could be tourney id or friendly room for mjs. appending to title instead to avoid 3->C etc. in tenhou.net/5
        res["lobby"] = 0

        # autism to fix logs with AI
        # ranks
        res["dan"] = [""] * nplayers
        for e in record.head.accounts:
            res["dan"][e.seat] = cfg["level_definition"]["level_definition"]["map_"][str(e.level.id)]["full_name_jp"]

        # level score, no real analog to rate
        res["rate"] = [0] * nplayers
        for e in record.head.accounts:
            res["rate"][e.seat] = e.level.score  # level score, closest thing to rate

        # sex
        res["sx"] = ['C'] * nplayers

        # >names
        res["name"] = ["AI"] * nplayers
        for e in record.head.accounts:
            res["name"][e.seat] = e.nickname

        # scores
        scores = [[e.seat, e.part_point_1, e.total_point / 1000] for e in record.head.result.players]
        res["sc"] = [0] * nplayers * 2
        for i, e in enumerate(scores):
            res["sc"][2 * e[0]] = e[1]
            res["sc"][2 * e[0] + 1] = e[2]

        # optional title - why not give the room and put the timestamp here
        res["title"] = [ruledisp + lobby, datetime.fromtimestamp(record.head.end_time).strftime("%Y-%m-%d %H:%M:%S")]

        wrapper = pb.Wrapper()
        wrapper.ParseFromString(record.data)

        details = pb.GameDetailRecords()
        details.ParseFromString(wrapper.data)

        converter = MajsoulPaipuParser(tsumoloss_off=tsumoloss_off)
        for act in details.actions:
            if len(act.result) != 0:
                round_record_wrapper = pb.Wrapper()
                round_record_wrapper.ParseFromString(act.result)

                log = getattr(pb, round_record_wrapper.name[len(".lq."):])()
                log.ParseFromString(round_record_wrapper.data)
                converter.feed(log)

                res["log"] = [e.dump() for e in converter.getvalue()]

        return res
