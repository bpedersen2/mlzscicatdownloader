#! /usr/bin/env python3

import os
from urllib.parse import quote_plus

import boto3
import jwt
import requests
from flask import Flask, Response, request
from zipstream import ZipStream
from requests_toolbelt import MultipartEncoder

app = Flask('downloader')

BACKEND_URL = os.environ.get('BACKEND_URL')
JWT_URL = '/auth/whoami'
DATASET_URL='/datasets/'
JWT_KEY = os.environ.get('JWT_SECRET')

@app.route('/zip', methods=['GET','POST'])
def zipper(*args):

    data = request.form
    directory = data['directory']
    files = []
    for k,v in data.items():
        if k.startswith('files'):
            files.append(v)

    auth_token = data['auth_token']
    jwt_token = f'Bearer {data["jwt"]}'
    try:
        jwtdata = jwt.decode(data['jwt'], JWT_KEY, algorithms=['HS256'])
    except jwt.exceptions.InvalidTokenError as ex:
        return '<html><body><div><h1>Token error!</h1><p>{ex.msg}</p></div></body></html>'
    valid = validate_jwt(data['jwt'])
    user = get_user_info(auth_token)
    acc = check_dataset_access(auth_token, data['dataset'])
    jac = check_dataset_access(jwt_token, data['dataset'])
    vf=validate_requested_files(acc.json(),auth_token, files, data['directory'])
    if request.args.get('debug', False) or not vf:
        return f"""<html><body><div>Download:
        <p>input: {data}</p>
        <p>jwt: {jwtdata}</p>
        <p> userinfo: {user}</p>
        <p>files: {files}</p>
        <p> jwt valid:  {valid}</p>
        <p> ds status: {acc.status_code} </p>
        <p> ds:{acc.json()}</p>
        <p> ds status(jwt): {jac.status_code} </p>
        <p> ds (jwt):{jac.json()}</p>
        <p> valid files: {vf}</div>
    <div></div></body></html>"""
    if len(vf)<5:
        return get_multiple_files(vf,directory)

    return get_zip_file(vf,directory)




def validate_jwt(jwt):
    res=requests.get(BACKEND_URL+JWT_URL, headers={"Authorization": f'Bearer {jwt}'})
    if res.status_code>300:
        return False
    return True

def check_dataset_access(at, pid):
    upid= quote_plus(pid)
    res=requests.get(BACKEND_URL+DATASET_URL+f'{upid}', headers={"Authorization": at})
    return res
    if res.status_code>300:
        return False
    return True

def get_user_info(at):
    res = requests.get(BACKEND_URL+JWT_URL,  headers={"Authorization": at})
    return res.json()

def validate_requested_files(ds,at, files, directory):
    if directory != ds.get('sourceFolder'):
        return False
    upid= quote_plus(ds['id'])

    res = requests.get(BACKEND_URL+DATASET_URL+f'{upid}/origdatablocks', headers={"Authorization": at})
    if res.status_code>300:
        return False

    datablocks=res.json()

    db_files=[]
    for b in datablocks:
        db_files += [f['path'] for f in b['dataFileList']]
    for f in  files:
        if f not in db_files:
            return False
    return files

def get_zip_file(files,directory):
    zs = gen_zip(files, directory)
    name= "mlz-data_download.zip"
    return Response(
        zs,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={name}.zip",
        }
    )

def gen_zip(files, directory):
    s3 = get_s3()
    # select bucket
    bucket = os.environ.get('AWS_DATA_BUCKET')

    zs = ZipStream()
    yield from zs.all_files()
    for file in files:
        filename = f'{file}'
        obj = s3.Object(bucket, filename).get()
        zs.add(obj['Body'].read(), filename)
        yield from zs.all_files()
    yield from zs.finalize()

def get_s3():
    s3session = boto3.Session(
        aws_access_key_id=os.environ.get('AWS_KEY'),
        aws_secret_access_key=os.environ.get("AWS_SECRET"),
        aws_session_token = None
    )
    #initiate s3 resource
    s3_ep = os.environ.get('AWS_ENDPOINT_URL')
    s3 = s3session.resource(
        's3', endpoint_url=s3_ep,
         config=boto3.session.Config(signature_version='s3v4',
          region_name=os.environ.get("AWS_REGION"),
          s3={"endpoint_url":s3_ep})
    )

    return s3

def get_multiple_files(files, directory):
    s3 = get_s3()
    bucket = os.environ.get('AWS_DATA_BUCKET')

    fields ={}
    for i,file in enumerate(files):
        filename = f'{file}'
        obj = s3.Object(bucket, filename).get()
        fields[f'file{i}'] =(filename, StreamingBodyWrapper(obj['Body']), obj['ContentType'] )

    m = MultipartEncoder(fields=fields)
    return Response(
        chunked_reader(m), content_type='message/rfc82', #m.content_type,
        headers={'Content-Length': m.len})

def chunked_reader(f, chunksize=2 ** 20):  # 1Mb chunks
    while True:
        chunk = f.read(chunksize)
        if not chunk:
            return
        yield chunk


class StreamingBodyWrapper(object):
    def __init__(self, sbody):
        self.sbody = sbody
        self.len = int(sbody._content_length)

    def read(self, chunk_size=0):
        chunk_size = chunk_size if chunk_size >= 0 else self.len
        chunk = self.sbody.read(chunk_size) or b''
        self.len -= len(chunk) if chunk else 0  # left to read

        return chunk