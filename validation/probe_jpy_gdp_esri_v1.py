#!/usr/bin/env python3
import urllib.request
url='https://www.esri.cao.go.jp/jp/sna/data/data_list/sokuhou/files/2019/qe191/tables/ritu-jk1911.csv'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
raw=urllib.request.urlopen(req,timeout=30).read()
for enc in ('cp932','shift_jis','utf-8-sig','utf-8'):
    try:
        txt=raw.decode(enc)
        print('ENCODING',enc)
        print('\n'.join(txt.splitlines()[:25]))
        break
    except Exception: pass
