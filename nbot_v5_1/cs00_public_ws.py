"""CS-00 reviewed-by-tests, PUBLIC USD-M TLS WebSocket transport.

Constructing this object never connects. Only an explicit future CS-01
owner-authorized caller can invoke connect after passing permit=True.
Routes are pinned to fstream.binance.com /public or /market streams.
NO keys, cookies, account/order endpoints, automatic reconnect or daemon.
RFC6455 bounded protocol: TLS hostname verified, HTTP 101 accept check,
client masking, server unmasked frame, ping/pong, finite payload, close HOLD.
"""
from __future__ import annotations
import base64
from hashlib import sha1
import os
import re
import secrets
import socket
import ssl
import struct
from urllib.parse import urlsplit

VERSION="NBOT_V5_1_CS00_PUBLIC_WSS_TRANSPORT_V1"
HOST="fstream.binance.com"
GUID="258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME=65536

class PublicSocketHold(ValueError):pass

def validate_route(uri:str):
    if type(uri) is not str or len(uri)>3000:
        raise PublicSocketHold("CS00_WSS_ROUTE_BOUNDS")
    p=urlsplit(uri)
    if (p.scheme!="wss" or p.hostname!=HOST or p.port not in (None,443)
         or p.username is not None or p.password is not None
         or p.fragment or p.path not in ("/public/stream","/market/stream")):
        raise PublicSocketHold("CS00_WSS_ENDPOINT_NOT_PUBLIC")
    if not p.query.startswith("streams="):
        raise PublicSocketHold("CS00_WSS_COMBINED_REQUIRED")
    parts=p.query[len("streams="):].split("/")
    if not 1<=len(parts)<=20 or any(not re.fullmatch(
        r"[a-z0-9]{3,24}@(aggTrade|bookTicker|markPrice@1s)",v) for v in parts):
        raise PublicSocketHold("CS00_WSS_STREAM_SET_INVALID")
    kinds={v.split("@",1)[1] for v in parts}
    if len(kinds)!=1:
        raise PublicSocketHold("CS00_WSS_MIXED_FEED_FORBIDDEN")
    kind=kinds.pop()
    expected_path="/public/stream" if kind=="bookTicker" else "/market/stream"
    if p.path!=expected_path:
        raise PublicSocketHold("CS00_WSS_PUBLIC_MARKET_PATH_MISMATCH")
    if len(parts)!=len(set(parts)):
        raise PublicSocketHold("CS00_WSS_DUPLICATE_SUBSCRIPTION")
    return p.path+"?"+p.query

def client_frame(payload:bytes,*,opcode:int=2,mask:bytes|None=None)->bytes:
    if type(payload) is not bytes or len(payload)>MAX_FRAME or opcode not in (2,8,9,10):
        raise PublicSocketHold("CS00_WSS_WRITE_FRAME_INVALID")
    key=secrets.token_bytes(4) if mask is None else mask
    if type(key) is not bytes or len(key)!=4:
        raise PublicSocketHold("CS00_WSS_MASK_INVALID")
    n=len(payload)
    header=bytes((0x80|opcode,0x80|n)) if n<=125 else (
        bytes((0x80|opcode,0x80|126))+struct.pack("!H",n))
    return header+key+bytes(x^key[i%4] for i,x in enumerate(payload))

class PublicTlsSocket:
    def __init__(self,uri:str,*,timeout_sec:int=10):
        self.request_target=validate_route(uri)
        if type(timeout_sec) is not int or not 1<=timeout_sec<=30:
            raise PublicSocketHold("CS00_WSS_TIMEOUT_CONFIG")
        self.timeout_sec=timeout_sec
        self.sock=None
        self.closed=True
        self.fragments=bytearray()
        self.fragment_opcode=None

    def connect(self,*,approved_cs01_public_only:bool=False):
        """Manual explicit call only. NEVER called during CS-00."""
        if approved_cs01_public_only is not True:
            raise PublicSocketHold("CS00_WSS_OWNER_CS01_APPROVAL_MISSING")
        if self.sock is not None:
            raise PublicSocketHold("CS00_WSS_ALREADY_CONNECTED")
        key=base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request=(
            f"GET {self.request_target} HTTP/1.1\r\n"
            f"Host: {HOST}\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "User-Agent: NBOT-V5.1-Public-Source-Only\r\n\r\n").encode("ascii")
        raw=None
        try:
            raw=socket.create_connection((HOST,443),timeout=self.timeout_sec)
            ctx=ssl.create_default_context()
            tls=ctx.wrap_socket(raw,server_hostname=HOST)
            tls.settimeout(self.timeout_sec)
            tls.sendall(request)
            header=bytearray()
            while b"\r\n\r\n" not in header:
                if len(header)>8192:
                    raise PublicSocketHold("CS00_WSS_HANDSHAKE_TOO_LARGE")
                char=tls.recv(1)
                if not char:raise PublicSocketHold("CS00_WSS_HANDSHAKE_CLOSED")
                header.extend(char)
            parts=bytes(header).split(b"\r\n")
            if parts[0]!=b"HTTP/1.1 101 Switching Protocols":
                raise PublicSocketHold("CS00_WSS_NOT_101")
            pairs={}
            for line in parts[1:]:
                if not line:break
                if b":" not in line:raise PublicSocketHold("CS00_WSS_BAD_HEADER")
                k,v=line.split(b":",1)
                k=k.strip().lower();v=v.strip()
                if k in pairs:raise PublicSocketHold("CS00_WSS_DUPLICATE_HEADER")
                pairs[k]=v
            expected=base64.b64encode(sha1((key+GUID).encode()).digest())
            if (pairs.get(b"sec-websocket-accept")!=expected
                or pairs.get(b"upgrade",b"").lower()!=b"websocket"
                or b"upgrade" not in pairs.get(b"connection",b"").lower()):
                raise PublicSocketHold("CS00_WSS_HANDSHAKE_ACCEPT_MISMATCH")
            self.sock=tls
            self.closed=False
        except Exception:
            if raw is not None:
                raw.close()
            self.sock=None
            self.closed=True
            raise

    def _exact(self,n):
        result=bytearray()
        while len(result)<n:
            chunk=self.sock.recv(n-len(result))
            if not chunk:
                self.closed=True
                raise PublicSocketHold("CS00_WSS_TRUNCATED_OR_DISCONNECTED")
            result.extend(chunk)
        return bytes(result)

    def read_message(self):
        if self.sock is None or self.closed:
            raise PublicSocketHold("CS00_WSS_NOT_CONNECTED_OR_HOLD")
        while True:
            try:
                first,second=self._exact(2)
                if first & 0x70 or second & 0x80:
                    raise PublicSocketHold("CS00_WSS_RESERVED_OR_MASKED_SERVER")
                fin=bool(first&0x80);opcode=first&0x0f
                n=second&0x7f
                if n==126:
                    n=struct.unpack("!H",self._exact(2))[0]
                    if n<126:raise PublicSocketHold("CS00_WSS_NONCANONICAL_SIZE")
                if n==127:
                    n=struct.unpack("!Q",self._exact(8))[0]
                    if n<65536:raise PublicSocketHold("CS00_WSS_NONCANONICAL_SIZE")
                if n>MAX_FRAME or len(self.fragments)+n>MAX_FRAME:
                    raise PublicSocketHold("CS00_WSS_OVERSIZED_FRAME")
                if opcode in (8,9,10) and (not fin or n>125):
                    raise PublicSocketHold("CS00_WSS_BAD_CONTROL_FRAME")
                payload=self._exact(n)
                if opcode==8:
                    self.closed=True
                    raise PublicSocketHold("CS00_WSS_SERVER_CLOSED")
                if opcode==9:
                    self.sock.sendall(client_frame(payload,opcode=10))
                    continue
                if opcode==10:continue
                if opcode in (1,2):
                    if self.fragment_opcode is not None:
                        raise PublicSocketHold("CS00_WSS_INTERLEAVED_FRAGMENT")
                    if fin:
                        if opcode!=1:
                            raise PublicSocketHold("CS00_WSS_BINANCE_JSON_TEXT_ONLY")
                        return payload
                    self.fragment_opcode=opcode
                    self.fragments.extend(payload)
                    continue
                if opcode==0 and self.fragment_opcode is not None:
                    self.fragments.extend(payload)
                    if fin:
                        if self.fragment_opcode!=1:
                            raise PublicSocketHold("CS00_WSS_BINANCE_JSON_TEXT_ONLY")
                        result=bytes(self.fragments)
                        self.fragments.clear();self.fragment_opcode=None
                        return result
                    continue
                raise PublicSocketHold("CS00_WSS_FRAME_OPCODE_INVALID")
            except (OSError,TimeoutError,PublicSocketHold) as exc:
                self.close()
                raise PublicSocketHold("CS00_WSS_SOURCE_GAP_RECONNECT_HOLD") from exc

    def close(self):
        s=self.sock;self.sock=None;self.closed=True
        self.fragments.clear();self.fragment_opcode=None
        if s is not None:
            try:s.close()
            except OSError:pass
