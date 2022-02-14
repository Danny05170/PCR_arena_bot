import sqlite3
import pandas as pd
from datetime import datetime

from ..dao.sqlitedao import DB_PATH

def get_data(gid: int, year:int, month: int) -> (str,pd.DataFrame):
    conn = sqlite3.connect(DB_PATH)
    month = str(month) if month>=10 else '0'+str(month)
    # get name
    command = f'SELECT * FROM clan'
    dt = pd.read_sql(command, conn)
    name = dt[dt["gid"]==gid]["name"].iloc[0]

    command = f'SELECT * FROM battle_{gid}_1_{year}{month}'
    dat = pd.read_sql(command, conn)

    conn.close()
    return name,dat

def get_person(gid: int, uid: int, year: int, month: int) -> (str,pd.DataFrame):

    name,dat = get_data(gid, year, month)
    dat = dat[dat["uid"] == uid]

    challenges = dat[["boss","dmg","flag"]]

    return name,challenges

def get_time(gid: int, year: int, month: int,uid:int) -> list:
    month = str(month) if month>=10 else '0'+str(month)
    conn = sqlite3.connect(DB_PATH)
    command = f'SELECT * FROM clan'
    dt = pd.read_sql(command, conn)
    name = dt[dt["gid"]==gid]["name"].iloc[0]
    
    if uid :
        command = f'SELECT time FROM battle_{gid}_1_{year}{month} WHERE uid={uid}'
    else:
        command = f'SELECT time FROM battle_{gid}_1_{year}{month}'    
    data = pd.read_sql(command,conn)
    print(data)

    def hour(ts: pd.Series):
        now = datetime.strptime(ts.iloc[0],"%Y-%m-%d %H:%M:%S.%f")
        return now.hour

    hours = data.apply(hour,result_type='reduce',axis=1).tolist()
    y = [0]*24
    for hr in hours:
        y[hr] += 1

    conn.close()
    return name,y



