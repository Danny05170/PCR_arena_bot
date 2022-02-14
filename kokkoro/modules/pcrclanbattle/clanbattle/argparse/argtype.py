import re

from kokkoro import util
from ..exception import ParseError
from ..battlemaster import BattleMaster

_unit_rate = {'': 1, 'k': 1000, 'w': 10000, '千': 1000, '萬': 10000}
_rex_dint = re.compile(r'^(\d+)([wk千萬]?)$', re.I)
_rex1_bcode = re.compile(r'^老?([1-5])王?$')
_rex2_bcode = re.compile(r'^老?([一二三四五])王?$')
_rex_rcode = re.compile(r'^[1-9]\d{0,2}$')

def damage_int(x:str) -> int:
    x = util.normalize_str(x)
    if m := _rex_dint.match(x):
        x = int(m.group(1)) * _unit_rate[m.group(2).lower()]
        cap = 200000000
        if x < cap:
            return x
    raise ParseError(f'傷害值不合法 傷害值應為小於{str(cap/100000000)+"e"}的非負整數')


def boss_code(x:str) -> int:
    x = util.normalize_str(x)
    if m := _rex1_bcode.match(x):
        return int(m.group(1))
    elif m := _rex2_bcode.match(x):
        return '零一二三四五'.find(m.group(1))
    raise ParseError('Boss編號不合法 應為1-5的整數')


def round_code(x:str) -> int:
    x = util.normalize_str(x)
    if _rex_rcode.match(x):
        return int(x)
    raise ParseError('周目數不合法 應為不大於999的非負整數')


def server_code(x:str) -> int:
    x = util.normalize_str(x)
    if x in ('jp', '日', '日服'):
        return BattleMaster.SERVER_JP
    elif x in ('tw', '台', '台服'):
        return BattleMaster.SERVER_TW
    elif x in ('cn', '國', '國服', 'b', 'b服'):
        return BattleMaster.SERVER_CN
    raise ParseError('未知服務器地區 請用jp/tw/cn')


def server_name(x:int) -> str:
    if x == BattleMaster.SERVER_JP:
        return 'jp'
    elif x == BattleMaster.SERVER_TW:
        return 'tw'
    elif x == BattleMaster.SERVER_CN:
        return 'cn'
    else:
        return 'unknown'

__all__ = [
    'damage_int', 'boss_code', 'round_code', 'server_code', 'server_name'
]
