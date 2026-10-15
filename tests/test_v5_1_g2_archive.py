"""G2 exact public REST byte custody, tamper, restart, quota and permission tests."""
from __future__ import annotations

import gzip
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.public_market import PublicResponse, PublicUsdMClient
from nbot_v5_1.source_archive import PublicSourceArchive, PublicArchiveHold, ARCHIVE_SCHEMA


class PublicSourceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nbot-g2-archive-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.archive=PublicSourceArchive(self.root)

    def response(self, *, payload=b'{"symbol":"BTCUSDT","price":"100.0"}',
                 kind="EXCHANGE_INFO", path="/fapi/v1/exchangeInfo",
                 received=1_000_000):
        import json
        return PublicResponse(kind,path,received,hashlib.sha256(payload).hexdigest(),
                              json.loads(payload),1,payload)

    def test_A01_serialize_exact_source_bytes_and_replay(self):
        self.assertEqual(ARCHIVE_SCHEMA,"NBOT_V5_1_PUBLIC_SOURCE_ARCHIVE_V1")
        receipt=self.archive.append(self.response())
        self.assertEqual(receipt.response.raw_bytes,self.response().raw_bytes)
        self.assertEqual(self.archive.replay(),(receipt,))
        self.assertEqual((self.root/receipt.name).stat().st_mode&0o777,0o600)
        self.assertEqual(self.archive.append(self.response()),receipt)

    def test_A02_tamper_gzip_and_partial_file_fail(self):
        receipt=self.archive.append(self.response())
        path=self.root/receipt.name
        path.write_bytes(b"\x1f\x8bgarbled")
        with self.assertRaises(PublicArchiveHold):self.archive.replay()
        with self.assertRaises(PublicArchiveHold):self.archive.append(self.response())

    def test_A03_orphan_and_unsafe_symlink_rejected(self):
        (self.root/"orphan.part").write_text("data")
        with self.assertRaises(PublicArchiveHold):self.archive.replay()
        (self.root/"orphan.part").unlink()
        fake=self.root/("source_"+"a"*64+".json.gz")
        fake.symlink_to("/etc/hosts")
        with self.assertRaises(PublicArchiveHold):self.archive.append(self.response())

    def test_A04_credential_order_or_nonpublic_uri_rejected(self):
        for kind,path in (("EXCHANGE_INFO","/fapi/v1/order"),
                          ("USER_DATA","/fapi/v1/userTrades"),
                          ("KLINES","https://other.invalid/fapi/v1/klines")):
            with self.subTest(kind=kind), self.assertRaises(PublicArchiveHold):
                self.archive.append(self.response(kind=kind,path=path))
        self.assertEqual(list(self.root.iterdir()),[])

    def test_A05_wrong_sha_or_no_raw_receipt_refused(self):
        p=self.response()
        from dataclasses import replace
        with self.assertRaises(PublicMarketErrorOrArchive()):
            self.archive.append(replace(p,raw_bytes=b""))
        with self.assertRaises(ValueError):
            replace(p,raw_bytes=b'{"wrong":true}')

    def test_A06_private_directory_required(self):
        self.root.chmod(0o777)
        try:
            with self.assertRaises(PublicArchiveHold):self.archive.append(self.response())
        finally:self.root.chmod(0o700)

    def test_A07_readonly_public_client_raw_bytes_equal_sha(self):
        c=PublicUsdMClient(allow_public_network=True,transport=lambda _:b'{"symbols":[]}',
                           now=lambda: 1000)
        result=c.exchange_info()
        self.assertEqual(result.raw_bytes,b'{"symbols":[]}')
        self.assertEqual(result.body_sha256,hashlib.sha256(result.raw_bytes).hexdigest())
        self.assertEqual(self.archive.append(result).response.body,result.body)

    def test_A08_quota_no_auto_delete(self):
        archive=PublicSourceArchive(self.root,budget_bytes=1024*1024)
        failed=False
        for i in range(300):
            # Incompressible-ish, fully deterministic public-only fixture.
            digits=hashlib.shake_256(str(i).encode()).hexdigest(4000).encode()
            p=self.response(received=i,payload=b'{"blob":"'+digits+b'"}')
            try: archive.append(p)
            except PublicArchiveHold as err:
                self.assertIn("FULL",str(err))
                failed=True
                break
        self.assertTrue(failed,"archive never exhausted its finite disk budget")
        self.assertGreater(len(archive.replay()),0)

    def test_A09_archive_does_not_create_directory_or_write_on_import(self):
        child=self.root/"missing"
        archive=PublicSourceArchive(child)
        self.assertFalse(child.exists())
        with self.assertRaises(PublicArchiveHold):archive.append(self.response())
        self.assertFalse(child.exists())

    def test_A10_changing_one_public_raw_byte_changes_receipt_identity(self):
        a=self.archive.append(self.response(payload=b'{"symbol":"BTCUSDT"}'))
        b=self.archive.append(self.response(payload=b'{"symbol":"ETHUSDT"}'))
        self.assertNotEqual(a.name,b.name)
        self.assertNotEqual(a.response.body_sha256,b.response.body_sha256)
        self.assertEqual(len(self.archive.replay()),2)


def PublicMarketErrorOrArchive():
    return PublicArchiveHold


if __name__=="__main__":
    unittest.main()
