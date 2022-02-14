from kokkoro.typing import List, Dict
from kokkoro.common_interface import EventInterface

from ..exception import *


class ArgHolder:
    __slots__ = ('type', 'default', 'tip')
    def __init__(self, type=str, default=None, tip=None):
        self.type = type
        self.default = default
        self.tip = tip


class ParseResult(dict):
    def __getattr__(self, key):
        return self.get(key, None)
    def __setattr__(self, key, value):
        self[key] = value


class ArgParser:
    def __init__(self, usage, arg_dict=None):
        self.usage = f"【用法/用例】\n{usage}\n\n※無需輸入尖括號，圓括號內為可選參數，用空格隔開命令與參數"
        self.arg_dict:Dict[str, ArgHolder] = arg_dict or {}


    def add_arg(self, name, *, type=str, default=None, tip=None):
        self.arg_dict[name] = ArgHolder(type, default, tip)
    
    
    def parse(self, args:List[str], ev:EventInterface) -> ParseResult:
        result = ParseResult()
        
        # 解析參數，以一個字符開頭，或無前綴
        for arg in args:
            if arg == '':
                continue
            name, x = arg[0].upper(), arg[1:]
            if name in self.arg_dict:
                holder = self.arg_dict[name]
            elif '' in self.arg_dict:
                holder = self.arg_dict['']
                name, x = '', arg
            else:
                raise ParseError(f'命令含有未知參數', self.usage)
            
            try:
                result.setdefault(name, holder.type(x))     # 多個參數只取第1個
            except ParseError as e:
                e.append(self.usage)
                raise e
            except Exception:
                msg = f"請給出正確的{holder.tip or '參數'}"
                if name:
                    msg += f"以{name}開頭"
                raise ParseError(msg, self.usage)
        
        # 檢查所有參數是否以賦值
        for name, holder in self.arg_dict.items():
            if name not in result:
                if holder.default is None:  # 缺失必要參數 拋異常
                    msg = f"請給出{holder.tip or '缺少的參數'}"
                    if name:
                        msg += f"以{name}開頭"
                    raise ParseError(msg, self.usage)
                else:
                    result[name] = holder.default
                    
        # 解析Message內的at
        mentions = ev.get_mentions()
        if (len(mentions) > 1):
            raise ParseError('請勿同時 at 多人')

        for user in mentions:
            result['uid'] = user.get_id()
            result['name'] = user.get_nick_name() or user.get_name()
        
        return result
