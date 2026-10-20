from hashlib import sha256
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nbot_v7.archive import download_inventory


class AcquisitionIntegrity(unittest.TestCase):
    def test_exchange_checksum_and_cached_corruption(self):
        payload=b"offline fake zip bytes for downloader integrity test only"
        checksum=sha256(payload).hexdigest()
        row={"symbol":"BTCUSDT","timeframe":"5m","month":"2026-01","bytes":len(payload),
             "key":"data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-01.zip"}
        def fetch(request,timeout=0):
            url=request if isinstance(request,str) else request.full_url
            return io.BytesIO((checksum+" filename.zip").encode() if url.endswith("CHECKSUM") else payload)
        with tempfile.TemporaryDirectory() as tmp,patch("nbot_v7.archive.urllib.request.urlopen",side_effect=fetch):
            root=Path(tmp)
            report=download_inventory({"objects":[row]},root,1)
            self.assertTrue(report["manifest_entries"][row["key"]]["exchange_checksum_verified"])
            self.assertTrue(download_inventory({"objects":[row]},root,1)["manifest_entries"][row["key"]]["cached"])
            file=root/"BTCUSDT"/"BTCUSDT-5m-2026-01.zip"
            file.write_bytes(b"x"*len(payload))
            with self.assertRaisesRegex(ValueError,"CHECKSUM_MISMATCH"):
                download_inventory({"objects":[row]},root,1)

    def test_manifest_cannot_escape_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"INVALID_ARCHIVE"):
                download_inventory({"objects":[{"symbol":"../escape","month":"2026-01","timeframe":"5m","bytes":1}]},Path(tmp),1)

if __name__=="__main__":unittest.main()
