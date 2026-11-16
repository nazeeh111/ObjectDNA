"""Per-request byte admission before a downstream multipart parser runs."""


class BoundedBodyMiddleware:
    def __init__(self, app, *, limit):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def refuse(status, message):
            body = ('{"detail":"' + message + '"}').encode("ascii")
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})

        lengths = [
            value.strip()
            for key, value in scope.get("headers", [])
            if key.lower() == b"content-length"
        ]
        if len(lengths) > 1 or (
            lengths and (not lengths[0] or len(lengths[0]) > 20 or not lengths[0].isdigit())
        ):
            return await refuse(400, "Invalid Content-Length.")
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > self.limit:
            return await refuse(413, "Request exceeds the 26 MiB total body limit.")

        body_buffer = bytearray()
        count = 0
        messages = 0
        while True:
            message = await receive()
            messages += 1
            if messages > 65536:
                return await refuse(413, "Request stream has too many fragments.")
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                return await refuse(400, "Invalid request stream.")
            body = message.get("body", b"")
            count += len(body)
            if count > self.limit:
                return await refuse(413, "Request exceeds the 26 MiB total body limit.")
            body_buffer.extend(body)
            if not message.get("more_body", False):
                break
        if declared is not None and declared != count:
            return await refuse(400, "Content-Length does not match the request body.")
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body_buffer), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
