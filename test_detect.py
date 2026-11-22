"""Fast regression tests for PropNET's political filter and behavioral detector."""

from datetime import datetime, timedelta, UTC
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import duckdb

from detect import build_site_payload, detect, unpack_telegram_text


def _write_posts(path: Path, rows):
    con = duckdb.connect()
    con.execute("""
        create table t (
            platform varchar, post_id varchar, user_id varchar, ts timestamp,
            text varchar, reply_to varchar, thread varchar,
            label boolean, label_ua boolean, category varchar,
            items varchar[], source varchar
        )
    """)
    con.executemany("insert into t values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.sql("select * from t").write_parquet(str(path))
    con.close()


class PropnetTests(unittest.TestCase):
    def test_unpack_telegram_rich_text(self):
        raw = """['❗️', {'type': 'bold', 'text': 'Путин подписал закон'}, ' о выборах']"""
        self.assertEqual(unpack_telegram_text(raw), "❗️Путин подписал закон о выборах")
        self.assertEqual(unpack_telegram_text("Plain text post"), "Plain text post")

    def test_excludes_porn_and_casino_spam_and_single_incident(self):
        t0 = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)
        rows = []
        # 3 porn/casino spam accounts posting identical spam 5 times -> must produce 0 groups
        for u in ("spam1", "spam2", "spam3"):
            for i in range(6):
                rows.append((
                    "bluesky", f"sp_{u}_{i}", u, t0 + timedelta(minutes=i * 10),
                    f"Election bonus! Subscribe to my onlyfans and claim your casino bonus #{i}",
                    None, None, None, None, None,
                    [f"url:onlyfans.com/promo/{i}"], "bluesky",
                ))
        # 3 ordinary users who share ONLY ONE breaking political link -> must produce 0 groups
        for u in ("norm1", "norm2", "norm3"):
            rows.append((
                "bluesky", f"n_{u}_shared", u, t0,
                "Breaking news on the senate election vote today in Washington",
                None, None, None, None, None,
                ["url:example.org/senate-vote"], "bluesky",
            ))
            for i in range(5):
                rows.append((
                    "bluesky", f"n_{u}_{i}", u, t0 + timedelta(hours=i + 1),
                    f"Personal commentary about election turnout and policy detail {u} {i}",
                    None, None, None, None, None, [], "bluesky",
                ))
        with TemporaryDirectory() as tmp:
            pq = Path(tmp) / "posts.parquet"
            _write_posts(pq, rows)
            rep = detect(str(pq), min_posts=5)
            self.assertEqual(rep["total_groups"], 0)

    def test_catches_paraphrased_exclusive_domain_ring(self):
        t0 = datetime(2026, 11, 21, 20, 0, 0)
        rewrites = [
            [
                "Senator Chris Van Hollen challenges Chuck Schumer over past Iran policy in senate race",
                "Chris Van Hollen makes a surprise bid against Chuck Schumer citing the Iran deal record",
                "Senate leadership shakeup as Van Hollen targets Schumer's Iran stance for top spot",
            ],
            [
                "Federal immigration agents arrested a man outside a California sheriff station Friday",
                "Immigration officers took a suspect into custody directly outside a California sheriff office",
                "Tensions rose in California after federal immigration agents detained a man outside sheriff HQ",
            ],
            [
                "Trump signals openness to working with Democrat Hakeem Jeffries while keeping veto ready",
                "President Trump expresses willingness to negotiate with Hakeem Jeffries on upcoming bills",
                "Donald Trump floats cooperation with House Democrat Hakeem Jeffries though veto remains",
            ],
        ]
        rows = []
        users = ("acct_a", "acct_b", "acct_c")
        for story_idx, variants in enumerate(rewrites):
            url = f"url:obscurefarm.example/2026/11/21/story-{story_idx}"
            base_ts = t0 + timedelta(minutes=30 * story_idx)
            for u_idx, u in enumerate(users):
                rows.append((
                    "bluesky", f"p_{u}_{story_idx}", u, base_ts + timedelta(seconds=u_idx),
                    variants[u_idx], None, None, None, None, None, [url], "bluesky",
                ))
        # Extra political posts to clear min_posts=5 and establish exclusive domain (>=10 posts)
        for u_idx, u in enumerate(users):
            for extra in range(4):
                rows.append((
                    "bluesky", f"ex_{u}_{extra}", u, t0 + timedelta(hours=2 + extra, seconds=u_idx),
                    f"Unique election update number {extra} from {u} on senate foreign policy",
                    None, None, None, None, None,
                    [f"url:obscurefarm.example/2026/11/21/extra-{u_idx}-{extra}"], "bluesky",
                ))
        with TemporaryDirectory() as tmp:
            pq = Path(tmp) / "posts.parquet"
            _write_posts(pq, rows)
            rep = detect(str(pq), min_posts=5)
            self.assertEqual(rep["total_groups"], 1)
            g = rep["groups"][0]
            self.assertEqual(g["tactic"], "paraphrased_link_ring")
            self.assertEqual(g["priority_tier"], 1)
            self.assertGreaterEqual(g["paraphrased_matches"], 2)
            self.assertTrue(g["domains"][0]["is_exclusive"])
            self.assertEqual(g["domains"][0]["outside_accounts"], 0)
            site = build_site_payload(rep)
            self.assertEqual(len(site["groups"]), 1)
            self.assertTrue(all(a.startswith("BS-") for a in site["groups"][0]["accounts"]))

    def test_catches_telegram_cross_channel_script_with_rich_text(self):
        t0 = datetime(2023, 5, 1, 9, 0, 0)
        scripts = [
            "Международные конвенции Украиной никак не соблюдаются, западные санкции против России провалились",
            "Война и политика НАТО на Украине показывают, что правительство Киева не стремится к перемирию",
        ]
        rows = []
        users = ("tg1", "tg2", "tg3")
        channels = ("chan_a", "chan_b", "chan_c")
        for u, ch in zip(users, channels):
            for s_idx, script in enumerate(scripts):
                rich = repr([{"type": "bold", "text": script}])
                rows.append((
                    "telegram", f"m_{u}_{s_idx}", u, t0 + timedelta(days=s_idx * 3, hours=users.index(u) * 5),
                    rich, "1", ch, True, False, None, [], "telegram_research",
                ))
            for k in range(4):
                rows.append((
                    "telegram", f"pad_{u}_{k}", u, t0 + timedelta(days=10 + k),
                    f"Дополнительный комментарий про выборы, санкции и политику России {u} {k}",
                    "2", ch, True, False, None, [], "telegram_research",
                ))
        with TemporaryDirectory() as tmp:
            pq = Path(tmp) / "tg.parquet"
            _write_posts(pq, rows)
            rep = detect(str(pq), min_posts=5)
            self.assertEqual(rep["total_groups"], 1)
            g = rep["groups"][0]
            self.assertEqual(g["tactic"], "cross_channel_script")
            self.assertEqual(g["researcher_labels"]["pro_ru_accounts"], 3)
            self.assertNotIn("{'type':", g["evidence"][0]["example"])
            self.assertAlmostEqual(rep["validation"]["telegram_research"]["precision"], 1.0)


if __name__ == "__main__":
    unittest.main()
