"""Bounded raw ASGI messages, before multipart parsing and session writes."""
import asyncio
import json
from objectdna.admission import BoundedBodyMiddleware


def exercise(messages, *, headers=(), limit=8):
    events=[];called=[];source=iter(messages)
    async def receive():
        try:return next(source)
        except StopIteration:return {'type':'http.disconnect'}
    async def send(event):events.append(event)
    async def downstream(scope, receive, send):
        called.append(await receive())
        await send({'type':'http.response.start','status':204,'headers':[]})
        await send({'type':'http.response.body','body':b''})
    asyncio.run(BoundedBodyMiddleware(downstream,limit=limit)({'type':'http','headers':list(headers)},receive,send))
    return events,called


def part(body,more=False):return {'type':'http.request','body':body,'more_body':more}


def test_exact_limit_and_chunked_overflow_without_content_length():
    events,called=exercise([part(b'1234',True),part(b'5678')]);assert events[0]['status']==204
    assert called==[part(b'12345678')]
    events,called=exercise([part(b'1234',True),part(b'56789')]);assert events[0]['status']==413 and not called


def test_declared_length_early_rejection_mismatch_and_malformed():
    for headers,expected in [([(b'content-length',b'9')],413), ([(b'content-length',b'7')],400), ([(b'content-length',b'3'),(b'content-length',b'3')],400), ([(b'content-length',b'-1')],400), ([(b'content-length',b'9'*100)],400)]:
        events,called=exercise([part(b'12345678')],headers=headers);assert events[0]['status']==expected and not called


def test_disconnect_and_empty_fragment_flood_do_not_reach_parser():
    events,called=exercise([part(b'12',True),{'type':'http.disconnect'}]);assert not events and not called
    events,called=exercise([part(b'',True)]*65537);assert events[0]['status']==413 and not called


def test_oversized_multipart_never_enters_parser_or_mutates_store_then_retry():
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from objectdna.api import app, STORE
    from objectdna.project import encode_project
    from test_project import source
    boundary='owned-test-boundary';project=encode_project(source())
    prefix=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="valid.json"\r\nContent-Type: application/json\r\n\r\n').encode()+project+b'\r\n'
    extra=(f'--{boundary}\r\nContent-Disposition: form-data; name="ignored"; filename="padding.bin"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
    suffix=f'\r\n--{boundary}--\r\n'.encode()
    def chunks():
        yield prefix;yield extra
        for _ in range(27*16):yield b'P'*65536
        yield suffix
    client=TestClient(app);before=list(STORE)
    with patch('starlette.formparsers.MultiPartParser.parse',side_effect=AssertionError('parser should not run')):
        response=client.post('/api/project/open',content=chunks(),headers={'Content-Type':'multipart/form-data; boundary='+boundary})
    assert response.status_code==413 and list(STORE)==before
    good=client.post('/api/project/open',files={'file':('valid.json',project,'application/json')})
    assert good.status_code==200 and good.json()['metrics']['valid']
