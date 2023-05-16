#! /usr/bin/env python3

from flask import Flask, request
import jwt

app = Flask('downloader')

@app.route('/zip', methods=['GET','POST'])
def zipper(*args):

    data = request.form
    files = []
    for k,v in data.items():
        if k.startswith('files'):
            files.append(v)

    jwtdata = jwt.decode(data['jwt'], 'ghfuersigersuhi', algorithms=['HS256'])
    return f"""<html><body><div>Download: <data> <jwtdata> {files} </div>
<div></div></body></html>"""



