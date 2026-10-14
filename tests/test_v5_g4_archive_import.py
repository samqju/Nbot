"""No-network G4 original Binance ZIP and checksum ingestion regression tests."""
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import unittest

from nbot.v5.g4_archive_import import ingest_verified_um_daily_zip

SYMBOL="XRPUSDT"
DATE="2026-10-12"
NAME=f"{SYMBOL}-aggTrades-{DATE}"
ROWS=[
    "10,1.2,5,10,10,1791763200000,false",
    "11,1.3,6,11,12,1791763201000,true",
    "12,1.4,7,13,13,1791763202000,false",
]
HEADER="agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker"


def fixture(rows=None, members=None):
    b=BytesIO()
    with ZipFile(b,"w",ZIP_DEFLATED) as z:
        for filename,data in members or [(NAME+".csv","\n".join(rows or ROWS)+"\n")]:
            z.writestr(filename,data)
    archive=b.getvalue()
    checksum=(sha256(archive).hexdigest()+"  "+NAME+".zip\n").encode()
    return archive,checksum


def ingest(modifier=None, rows=None, members=None):
    archive,checksum=fixture(rows=rows,members=members)
    if modifier:
        archive,checksum=modifier(archive,checksum)
    return ingest_verified_um_daily_zip(archive_bytes=archive,
        checksum_bytes=checksum,symbol=SYMBOL,on_date=DATE,
        captured_at_ms=1791963300000)


class ArchiveImportTests(unittest.TestCase):
    def test_original_headers_and_rows_canonical(self):
        m,rows=ingest(rows=[HEADER]+ROWS)
        self.assertEqual(m["row_count"],3)
        self.assertEqual(m["first_agg_id"],10)
        self.assertEqual(m["last_agg_id"],12)
        self.assertEqual([x["m"] for x in rows],[False,True,False])
        self.assertEqual(m["symbol"],SYMBOL)
        self.assertIn("data.binance.vision",m["archive_url"])

    def test_source_hash_binding_but_no_fake_provenance(self):
        manifest,_=ingest()
        self.assertEqual(manifest["original_archive_verified"],False)
        self.assertEqual(manifest["origin_and_custody_independently_verified"],False)
        self.assertEqual(len(manifest["archive_sha256"]),64)
        self.assertEqual(len(manifest["checksum_source_sha256"]),64)

    def test_deterministic_reingestion_of_same_archive(self):
        self.assertEqual(ingest(),ingest())

    def test_changed_zip_content_checksum_detected(self):
        def corrupt(a,c):
            return a+b"not_original",c
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_SHA256_MISMATCH"):
            ingest(corrupt)

    def test_wrong_checksum_filename_rejected(self):
        def altered(a,c):
            return a,c.replace((NAME+".zip").encode(),b"BTCUSDT-aggTrades-2026-10-12.zip")
        with self.assertRaisesRegex(ValueError,"G4_CHECKSUM_IDENTITY_INVALID"):
            ingest(altered)

    def test_unsigned_or_missing_checksum_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_CHECKSUM_SOURCE_MISSING"):
            ingest(lambda a,c:(a,b""))

    def test_wrong_csv_member_name_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_UNSUPPORTED_CONTENT"):
            ingest(members=[("../outside.csv","\n".join(ROWS))])

    def test_multiple_zip_members_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_UNSUPPORTED_CONTENT"):
            ingest(members=[(NAME+".csv","\n".join(ROWS)),("extra.txt","untrusted")])

    def test_invalid_csv_record_width_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_CSV_SHAPE_INVALID"):
            ingest(rows=[ROWS[0], "11,1.3,6,11,12,1791763201000",ROWS[2]])

    def test_aggtrade_id_gap_rejected(self):
        rows=[ROWS[0],ROWS[1].replace("11,1.3","15,1.3"),ROWS[2]]
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_CSV_SEQUENCE_INVALID"):
            ingest(rows=rows)

    def test_underlying_trade_id_gap_retained_as_explicit_research_hold(self):
        rows=[ROWS[0],ROWS[1].replace(",11,12,179",",13,14,179"),
              ROWS[2].replace(",13,13,179",",15,15,179")]
        m,parsed=ingest(rows=rows)
        self.assertEqual(len(parsed),3)
        self.assertEqual(m["underlying_trade_id_gap_count"],1)
        self.assertEqual(m["underlying_trade_ids_missing"],2)
        self.assertFalse(m["all_underlying_trade_ids_contiguous"])
        self.assertEqual(m["research_path_grade"],"HOLD_UNDERLYING_TRADE_ID_GAPS")
        self.assertEqual(m["original_archive_verified"],False)

    def test_underlying_trade_id_rewind_still_rejected(self):
        rows=[ROWS[0],ROWS[1].replace(",11,12,179",",10,12,179"),ROWS[2]]
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_CSV_SEQUENCE_INVALID"):
            ingest(rows=rows)

    def test_backward_trade_time_rejected(self):
        rows=[ROWS[0],ROWS[1],ROWS[2].replace("1791763202000","1791763200500")]
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_CSV_SEQUENCE_INVALID"):
            ingest(rows=rows)

    def test_nonboolean_maker_flag_rejected(self):
        rows=[ROWS[0],ROWS[1].replace(",true",",1"),ROWS[2]]
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_CSV_MAKER_FLAG_INVALID"):
            ingest(rows=rows)

    def test_invalid_capture_clock_rejected(self):
        a,c=fixture()
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_CAPTURE_CLOCK_INVALID"):
            ingest_verified_um_daily_zip(archive_bytes=a,checksum_bytes=c,
                symbol=SYMBOL,on_date=DATE,captured_at_ms=0)

    def test_date_and_symbol_rejected_without_fetch(self):
        a,c=fixture()
        for symbol,date in [("../XRP","2026-10-12"),(SYMBOL,"12-10-2026")]:
            with self.assertRaises(ValueError):
                ingest_verified_um_daily_zip(archive_bytes=a,checksum_bytes=c,
                    symbol=symbol,on_date=date,captured_at_ms=1)

    def test_truncated_zip_is_not_source(self):
        a,c=fixture()
        damaged=a[:24]
        check=(sha256(damaged).hexdigest()+"  "+NAME+".zip\n").encode()
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_BAD_ZIP_OR_ENCODING"):
            ingest_verified_um_daily_zip(archive_bytes=damaged,checksum_bytes=check,
                symbol=SYMBOL,on_date=DATE,captured_at_ms=1)

    def test_valid_checksum_but_wrong_trade_day_is_rejected(self):
        bad=[ROWS[0],ROWS[1].replace("1791763201000","1791849601000"),ROWS[2]]
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_TRADE_DATE_MISMATCH"):
            ingest(rows=bad)

    def test_valid_checksum_but_negative_price_is_rejected(self):
        bad=[ROWS[0],ROWS[1].replace(",1.3,6,",",-1.3,6,"),ROWS[2]]
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_PRICE_QTY_INVALID"):
            ingest(rows=bad)

    def test_same_day_not_yet_finalized_rejected(self):
        a,c=fixture()
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_NOT_YET_FINALIZED"):
            ingest_verified_um_daily_zip(archive_bytes=a,checksum_bytes=c,
                symbol=SYMBOL,on_date=DATE,captured_at_ms=1791763300000)

    def test_single_row_does_not_qualify_continuous_path(self):
        with self.assertRaisesRegex(ValueError,"G4_ARCHIVE_TOO_FEW_TRADES"):
            ingest(rows=[ROWS[0]])


if __name__=="__main__":
    unittest.main()
