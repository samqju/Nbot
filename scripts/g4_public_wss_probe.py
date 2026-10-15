"""One-shot bounded PUBLIC USD-M WSS 20-market source audit; NO service.

Explicit CLI opt-in only. No account/order endpoints, api keys, sockets on
import, unbounded logs or permanent installation. Actual public TLS WSS
source samples are independently hash replayed and then the TEMP audit
directory is removed. Sampling does not establish uninterrupted 24h service
or signed original quote/fill/settled funding evidence.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import ssl
import struct
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))

from nbot_v5_1.deep_source import stream_urls,DeepSourceHold
from nbot_v5_1.deep_segments import DeepSegmentRecorder,DeepSegmentHold
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.deep_selection import choose_deep
from g2_readonly_probe import probe
from nbot_v5_1.source_archive import PublicSourceArchive

HOST="fstream.binance.com"
MAX_HTTP_HANDSHAKE=16384
MAX_FRAME=65536


class WssHold(ValueError):pass


class ExactReader:
    def __init__(self,sock,leftover=b""):
        self.sock=sock
        self.left=leftover
    def take(self,n):
        out=self.left[:n]
        self.left=self.left[n:]
        while len(out)<n:
            b=self.sock.recv(n-len(out))
            if not b:raise WssHold("G4_TLS_STREAM_CLOSED")
            out+=b
        return out


def _connect(url):
    target=urlsplit(url)
    if target.scheme!="wss" or target.netloc!=HOST or target.path not in (
            "/public/stream","/market/stream"):
        raise WssHold("G4_FORBIDDEN_WSS_ENDPOINT")
    key=base64.b64encode(os.urandom(16)).decode()
    tcp=socket.create_connection((HOST,443),timeout=8)
    try:
        tls=ssl.create_default_context().wrap_socket(tcp,server_hostname=HOST)
        tls.settimeout(5)
        uri=target.path+"?"+target.query
        req=(f"GET {uri} HTTP/1.1\r\nHost: {HOST}\r\n"
             "Upgrade: websocket\r\nConnection: Upgrade\r\n"
             f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        tls.sendall(req.encode("ascii"))
        header=b""
        while b"\r\n\r\n" not in header and len(header)<MAX_HTTP_HANDSHAKE:
            chunk=tls.recv(4096)
            if not chunk:raise WssHold("G4_HANDSHAKE_CLOSED")
            header+=chunk
        if b"\r\n\r\n" not in header:raise WssHold("G4_HANDSHAKE_HEADER_OVERSIZE")
        head,left=header.split(b"\r\n\r\n",1)
        parts=head.decode("iso-8859-1").split("\r\n")
        status=parts[0]
        headers={}
        for line in parts[1:]:
            if ":" not in line:raise WssHold("G4_BAD_HANDSHAKE_HEADER")
            k,v=line.split(":",1);headers[k.lower()]=v.strip()
        expected=base64.b64encode(hashlib.sha1((key+
                  "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if (" 101 " not in status or headers.get("sec-websocket-accept")!=expected
                or headers.get("upgrade","").lower()!="websocket"):
            raise WssHold("G4_TLS_WEBSOCKET_UPGRADE_INVALID")
        return tls,ExactReader(tls,left)
    except Exception:
        tcp.close()
        raise


def _pong(sock,payload):
    if len(payload)>125:raise WssHold("G4_CONTROL_TOO_LONG")
    mask=os.urandom(4)
    data=bytes(b^mask[i%4] for i,b in enumerate(payload))
    sock.sendall(bytes([0x8A,0x80|len(payload)])+mask+data)


def _recv(reader):
    a,b=reader.take(2)
    opcode=a&0x0F
    if a&0x70 or not a&0x80 or b&0x80:
        raise WssHold("G4_FRAGMENT_EXTENSION_OR_MASK_INVALID")
    size=b&127
    if size==126:size=int.from_bytes(reader.take(2),"big")
    if size==127:size=int.from_bytes(reader.take(8),"big")
    if size>MAX_FRAME:raise WssHold("G4_WEBSOCKET_FRAME_OVER_LIMIT")
    payload=reader.take(size)
    if opcode not in (1,2,8,9,10):
        raise WssHold("G4_WEBSOCKET_OPCODE_INVALID")
    return opcode,payload


def _capture(symbols,archive:Path,seconds_per_route=5):
    if not 1<=seconds_per_route<=12:raise WssHold("G4_WSS_PROBE_DURATION_INVALID")
    recorder=DeepSegmentRecorder(archive,symbols=symbols,budget_bytes=64*1024*1024) if False else DeepSegmentRecorder(archive,symbols=symbols,quota_bytes=64*1024*1024)
    urls=stream_urls(symbols)
    result={}
    all_hold=[]
    for kind,url in urls.items():
        seen=set();valid=invalid=0
        socket_status="CONNECTING"
        raw_sock=None
        try:
            raw_sock,reader=_connect(url)
            raw_sock.settimeout(1.0)
            start=time.monotonic()
            while time.monotonic()-start<seconds_per_route and valid+invalid<25000:
                try:opcode,data=_recv(reader)
                except (TimeoutError,socket.timeout):continue
                if opcode==8:break
                if opcode==9:_pong(raw_sock,data);continue
                if opcode==10:continue
                if opcode!=1:
                    invalid+=1;continue
                clock=int(time.time()*1000)
                if recorder.queued_bytes+len(data)>440000:
                    recorder.flush()
                try:
                    ev=recorder.append(kind=kind,raw=data,received_at_ms=clock,epoch=1)
                except (DeepSourceHold,DeepSegmentHold) as exc:
                    invalid+=1
                    if len(all_hold)<15:all_hold.append(kind+":"+str(exc)[:85])
                    continue
                valid+=1;seen.add(ev.symbol)
            socket_status="OK" if valid else "NO_VALID_PUBLIC_FRAMES"
        except (OSError,ssl.SSLError,WssHold,ValueError) as exc:
            socket_status="SOURCE_HOLD:"+type(exc).__name__+":"+str(exc)[:90]
            if len(all_hold)<15:all_hold.append(kind+":"+socket_status)
        finally:
            if raw_sock is not None:raw_sock.close()
        result[kind]={"status":socket_status,"received_valid":valid,
                 "rejected":invalid,"symbols_with_frames":len(seen),
                 "unseen_symbols":sorted(set(symbols)-seen)[:20]}
    recorder.flush()
    replay,head,n=recorder.replay()
    expected=sum(item["received_valid"] for item in result.values())
    if len(replay)!=expected:
        raise WssHold("G4_PUBLIC_SOURCE_REPLAY_COUNT_MISMATCH")
    return {"source_types":result,"selected":len(symbols),"btc_included":"BTCUSDT" in symbols,
            "raw_valid_messages":expected,"segments":n,
            "raw_source_replayed":len(replay),"last_segment_hash":head,
            "bytes_on_disk":sum(p.stat().st_size for p in archive.iterdir()),
            "errors_sample":all_hold,
            "all_20_triple_channel_warm":all(
                 item["symbols_with_frames"]==20 and item["rejected"]==0
                 for item in result.values()),
            "continuous_5m_witness_proven":False,
            "settled_funding_proven":False,
            "cryptographic_exchange_signature_proven":False,
            "financial_authority":"NONE"}


def run(*,enabled:bool,seconds_per_route:int=5)->dict:
    if type(enabled) is not bool or not enabled:
        raise WssHold("G4_PUBLIC_NETWORK_OPT_IN_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="nbot-g4-wss-smoke-") as tmp:
        root=Path(tmp)
        source_root=root/"source"
        source_root.mkdir(mode=0o700)
        capture_root=root/"g4"
        capture_root.mkdir(mode=0o700)
        rest=PublicSourceArchive(source_root,budget_bytes=64*1024*1024)
        def callback(book,event):
            g3=explore_event(book,event,capacity_slots=0)
            selected=choose_deep(book.manifest,g3)
            return {"deep_digest":selected.manifest_sha,
                    "selected_symbols":list(selected.symbols),
                    "all_20_warmup_hold":all(
                         r.state=="SELECTED_WARMUP_HOLD" for r in selected.entries),
                    "wss":_capture(selected.symbols,capture_root,seconds_per_route)}
        output=probe(enabled=True,max_history_requests=130,
                     archive=rest,on_event=callback)
        output["g4"]="TEMP_READONLY_SOURCE_SAMPLE_NOT_FULL_G4_ACCEPTANCE"
        # Full test directory and every raw frame removed on normal exit.
        return output

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--public-network",action="store_true")
    parser.add_argument("--seconds-per-route",type=int,default=5)
    args=parser.parse_args()
    try:
        output=run(enabled=args.public_network,
                   seconds_per_route=args.seconds_per_route)
        print(json.dumps(output,sort_keys=True),flush=True)
        print("G4_TEMP_PUBLIC_RAW_SOURCE_ARCHIVE_REMOVED",flush=True)
    except (WssHold,DeepSourceHold,DeepSegmentHold,ValueError,ssl.SSLError,OSError) as exc:
        print(json.dumps({"status":"G4_PUBLIC_SOURCE_HOLD",
                          "reason":type(exc).__name__+":"+str(exc),
                          "no_orders":True}),flush=True)
        sys.exit(2)
