import re
import json
import os
import pytz
from functools import wraps
from collections import defaultdict

import kokkoro
from kokkoro import logger
from kokkoro import priv, log, typing, trigger
from kokkoro.typing import *
from kokkoro.common_interface import *
from kokkoro.bot import get_scheduler, get_bot
from kokkoro.util import join_iterable
from kokkoro.platform_patch import check_platform

# service management
_loaded_services: Dict[str, "Service"] = {}  # {name: service}
_loaded_bc_services: Dict[str, "Service"] = {}  # {name: service}
_re_illegal_char = re.compile(r'[\\/:*?"<>|\.]')
_service_config_dir = os.path.expanduser('~/.kokkoro/service_config/')
os.makedirs(_service_config_dir, exist_ok=True)

def _load_service_config(service_name):
    config_file = os.path.join(_service_config_dir, f'{service_name}.json')
    if not os.path.exists(config_file):
        return {}  # config file not found, return default config.
    try:
        with open(config_file, encoding='utf8') as f:
            config = json.load(f)
            return config
    except Exception as e:
        logger.exception(e)
        return {}

def _save_service_config(service):
    config_file = os.path.join(_service_config_dir, f'{service.name}.json')
    body = {
                "name": service.name,
                "use_priv": service.use_priv,
                "manage_priv": service.manage_priv,
                "broadcast_tag": service.broadcast_tag,
                "enable_on_default": service.enable_on_default,
                "visible": service.visible,
                "enable_group": list(service.enable_group),
                "disable_group": list(service.disable_group),
            }
    if isinstance(service, BroadcastService):
        body["group_bc_tag"] = service.group_bc_tag

    with open(config_file, 'w', encoding='utf8') as f:
        json.dump(
            body,
            f,
            ensure_ascii=False,
            indent=2)

class ServiceFunc:
    def __init__(self, sv: "Service", func: Callable, only_to_me: bool):
        self.sv = sv
        self.func = func
        self.only_to_me = only_to_me
        self.__name__ = func.__name__

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

class BroadcastTag:
    cn_broadcast = "????????????"
    tw_broadcast = "????????????"
    jp_broadcast = "????????????"
    rank_broadcast = "????????????"
    farm_broadcast = "d????????????"
    drug_broadcast = ""
    default = config.DEFAULT_BROADCAST_TAG

    @staticmethod
    def parse(key):
        if key == "cn_broadcast":
            return BroadcastTag.cn_broadcast
        elif key == "tw_broadcast":
            return BroadcastTag.tw_broadcast
        elif key == "jp_broadcast":
            return BroadcastTag.jp_broadcast
        elif key == "rank_broadcast":
            return BroadcastTag.rank_broadcast  
        elif key == "farm_broadcast":
            return BroadcastTag.farm_broadcast     
    #    elif key == "drug_broadcast":
     #       return BroadcastTag.drug_broadcast       
        else:
            return BroadcastTag.default

class Service:
    """??????????????????????????????, ????????????????????????????????????????????????.

    ?????????????????????:
    `on_message`,
    `on_prefix`, `on_fullmatch`, `on_suffix`,
    `on_keyword`, `on_rex`,
    `on_command`, `on_natural_language`

    ???????????????
    `scheduled_job`, `broadcast`

    ?????????????????????????????????
    {
        "name": "ServiceName",
        "use_priv": priv.NORMAL,
        "manage_priv": priv.ADMIN,
        "enable_on_default": true/false,
        "visible": true/false,
        "enable_group": [],
        "disable_group": []
    }

    ???????????????
    `~/.kokkoro/service_config/{ServiceName}.json`
    """
    def __init__(self, name, use_priv=None, manage_priv=None, broadcast_tag=None, enable_on_default=None, visible=None,
                 help_=None):
        """
        ??????????????????
        ???????????????????????????????????? > ???????????? > ?????????
        """
        #assert not _re_illegal_char.search(name), r'Service name cannot contain character in `\/:*?"<>|.`'

        config = _load_service_config(name)
        self._loaded_config = config # for sub-class init
        self.name = name
        self.use_priv = config.get('use_priv') or use_priv or priv.NORMAL
        self.manage_priv = config.get('manage_priv') or manage_priv or priv.ADMIN
        self.enable_on_default = config.get('enable_on_default')
        self.broadcast_tag = config.get('broadcast_tag') or broadcast_tag or BroadcastTag.default # default tag for  group bc tag
        if isinstance(self.broadcast_tag, str):
            self.broadcast_tag = [self.broadcast_tag]
        if self.enable_on_default is None:
            self.enable_on_default = enable_on_default
        if self.enable_on_default is None:
            self.enable_on_default = True
        self.visible = config.get('visible')
        if self.visible is None:
            self.visible = visible
        if self.visible is None:
            self.visible = True
        self.help = help_
        self.enable_group = set(config.get('enable_group', []))
        self.disable_group = set(config.get('disable_group', []))

        self.logger = log.new_logger(name)

        assert self.name not in _loaded_services, f'Service name "{self.name}" already exist!'
        _loaded_services[self.name] = self

    @property
    def bot(self):
        return get_bot()
    
    @property
    def scheduler(self):
        return get_scheduler()
    
    @staticmethod
    def get_loaded_services() -> Dict[str, "Service"]:
        return _loaded_services
    
    def set_enable(self, group_id):
        self.enable_group.add(group_id)
        self.disable_group.discard(group_id)
        _save_service_config(self)
        self.logger.info(f'Service {self.name} is enabled at group {group_id}')

    def set_disable(self, group_id):
        self.enable_group.discard(group_id)
        self.disable_group.add(group_id)
        _save_service_config(self)
        self.logger.info(
            f'Service {self.name} is disabled at group {group_id}')

    def check_enabled(self, group_id):
        return bool( (group_id in self.enable_group) or (self.enable_on_default and group_id not in self.disable_group))


    def _check_all(self, ev: EventInterface):
        gid = ev.get_group_id()
        return self.check_enabled(gid) and not priv.check_block_group(gid) and priv.check_priv(ev.get_author(), self.use_priv)
    
    def get_enable_groups(self) -> dict:
        """?????????????????????????????????
        @return [group_id]
        """
        gl = defaultdict(list)
        gids = set(g.get_id() for g in self.bot.get_groups())
        if self.enable_on_default:
            gids = gids - self.disable_group
        else:
            gids = gids & self.enable_group
        return gids

    def on_prefix(self, prefix, only_to_me=False) -> Callable:
        if isinstance(prefix, str):
            prefix = (prefix, )
        @check_platform
        def deco(func) -> Callable:
            sf = ServiceFunc(self, func, only_to_me)
            for p in prefix:
                trigger.prefix.add(p, sf)
            return func
        return deco
    
    def on_fullmatch(self, word, only_to_me=False) -> Callable:
        if isinstance(word, str):
            word = (word, )
        @check_platform
        def deco(func) -> Callable:
            @wraps(func)
            async def wrapper(bot: KokkoroBot, ev: EventInterface):
                param = ev.get_param()
                if param.remain != '':
                    self.logger.info(f'Message {ev.get_id()} is ignored by fullmatch condition.')
                    return
                return await func(bot, ev)
            sf = ServiceFunc(self, wrapper, only_to_me)
            for w in word:
                trigger.prefix.add(w, sf)
            return func
            # func itself is still func, not wrapper. wrapper is a part of trigger.
            # so that we could use multi-trigger freely, regardless of the order of decorators.
            # ```
            # """the order doesn't matter"""
            # @on_keyword(...)
            # @on_fullmatch(...)
            # async def func(...):
            #   ...
            # ```
        return deco
    
    def on_suffix(self, suffix, only_to_me=False) -> Callable:
        if isinstance(suffix, str):
            suffix = (suffix, )
        @check_platform
        def deco(func) -> Callable:
            sf = ServiceFunc(self, func, only_to_me)
            for s in suffix:
                trigger.suffix.add(s, sf)
            return func
        return deco

    def on_keyword(self, keywords, only_to_me=False) -> Callable:
        if isinstance(keywords, str):
            keywords = (keywords, )
        @check_platform
        def deco(func) -> Callable:
            sf = ServiceFunc(self, func, only_to_me)
            for kw in keywords:
                trigger.keyword.add(kw, sf)
            return func
        return deco

    def on_rex(self, rex: Union[str, re.Pattern], only_to_me=False) -> Callable:
        if isinstance(rex, str):
            rex = re.compile(rex)
        @check_platform
        def deco(func) -> Callable:
            sf = ServiceFunc(self, func, only_to_me)
            trigger.rex.add(rex, sf)
            return func
        return deco

    def scheduled_job(self, *args, **kwargs) -> Callable:
        kwargs.setdefault('timezone', pytz.timezone('Asia/Shanghai'))
        kwargs.setdefault('coalesce', True)
        if config.BOT_TYPE == "tomon":
            #FIXME: Tomon ?????????????????????????????????????????????????????????
            kwargs.setdefault('misfire_grace_time', 5*60)
        else:
            kwargs.setdefault('misfire_grace_time', 60)

        @check_platform
        def deco(func: Callable) -> Callable:
            kokkoro.logger.debug(f'{func.__name__} registered to scheduler')
            @wraps(func)
            async def wrapper():
                try:
                    self.logger.info(f'Scheduled job {func.__name__} start.')
                    ret = await func()
                    self.logger.info(f'Scheduled job {func.__name__} completed.')
                    return ret
                except Exception as e:
                    self.logger.error(f'{type(e)} occured when doing scheduled job {func.__name__}.')
                    self.logger.exception(e)
            return self.scheduler.scheduled_job(*args, **kwargs)(wrapper)
        return deco


class BroadcastService(Service):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = self._loaded_config
        self.group_bc_tag = config.get('group_bc_tag', {})
        #service_names = (self.name,)       
         
        set_prefix = f'{self.name} set-bc-tag' #join_iterable(service_names, ('bc-tag',), sep=' ')
        get_prefix = f'{self.name} get-bc-tag'

        

        async def set_bc_tag(bot, ev):
            if not priv.check_priv(ev.get_author(), priv.ADMIN):
                await bot.kkr_send(ev, f'???????????????????????????????????????????????? 0x0')
                return
            gid = ev.get_group_id()
            new_tags = ev.get_param().remain
            if new_tags in ['', None]:
                await bot.kkr_send(ev, f'??????????????? <{self.name}> ????????????????????????\n??????????????????????????????')
                return
            new_tags = new_tags.split(' ')
            self.set_broadcast_tag(gid, new_tags)

            await bot.kkr_send(ev, f'?????? <{self.name}> ??????????????????????????????????????? {new_tags}')

        async def get_bc_tag(bot, ev):
            gid = ev.get_group_id()
            await bot.kkr_send(ev, f'?????? <{self.name}> ??????????????????????????? {self.group_bc_tag.get(gid, self.broadcast_tag)}')

        self.on_prefix(set_prefix)(set_bc_tag)
        self.on_prefix(get_prefix)(get_bc_tag)

        _loaded_bc_services[self.name] = self
    
    def set_broadcast_tag(self, gid, new_tags):
        if isinstance(new_tags, str):
            new_tags = (new_tags,)

        self.group_bc_tag[gid] = new_tags

        _save_service_config(self)
        self.logger.info(f'Service {self.name}\'s broadcast tag of group {gid} is modified as {new_tags}')
    
    async def broadcast(self, msg: SupportedMessageType):
        bot = self.bot
        glist = self.get_enable_groups()

        for gid in glist:
            tag = self.group_bc_tag.get(gid, self.broadcast_tag)
            
            try:
                for t in tag:
                    print(t)
                    await bot.kkr_send_by_group(gid, msg, t)
                    self.logger.info(f"???{gid} ??????{t}?????? ")
            except Exception as e:
                self.logger.error(f"???{gid} ??????{tag}?????????{type(e)}")
                self.logger.exception(e)

    @staticmethod
    def get_loaded_bc_services() -> Dict[str, "Service"]:
        return _loaded_bc_services