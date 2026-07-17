import unittest
from unittest.mock import AsyncMock, patch

import server


class FactCheckTests(unittest.IsolatedAsyncioTestCase):
    def test_concise_text_keeps_a_complete_sentence_when_possible(self):
        text = "This first sentence is clear. " + "word " * 50
        self.assertEqual(server.concise_text(text, 12), "This first sentence is clear.")
        self.assertLessEqual(len(server.concise_text("word " * 50, 12).split()), 12)
        abbreviation = "The claim about Washington, D.C. is disputed. The claim about Washington, D.C. needs more context."
        self.assertEqual(
            server.concise_text(abbreviation, 12),
            "The claim about Washington, D.C. is disputed.",
        )
        evidence = [{"summary": "word " * 50, "sources": list(range(10))}] * 3
        concise = server.concise_evidence(evidence)
        self.assertEqual(len(concise), 2)
        self.assertEqual(len(concise[0]["sources"]), 4)

    def test_thumbnail_url_uses_platform_field_and_rejects_unsafe_urls(self):
        self.assertEqual(
            server.thumbnail_url("instagram", {"thumbnailUrl": "https://example.com/post.jpg"}),
            "https://example.com/post.jpg",
        )
        self.assertEqual(
            server.thumbnail_url("x", {"img": "http://example.com/post.jpg"}),
            "http://example.com/post.jpg",
        )
        self.assertIsNone(server.thumbnail_url("youtube", {"thumbnail": "javascript:alert(1)"}))

    def test_youtube_cache_key_keeps_video_id_only(self):
        self.assertEqual(
            server.normalize_url("https://www.youtube.com/watch?v=abc123&si=tracking#fragment"),
            "https://www.youtube.com/watch?v=abc123",
        )

    async def test_invalid_json_retries_and_keeps_last_raw_answer(self):
        responses = [
            {"answers": ["not json"]},
            {"answers": ["still not json"]},
            {"answers": ['{"claims": ["A claim", "B claim", "C claim"]}']},
        ]
        with patch("server.chat_with_retry", AsyncMock(side_effect=responses)) as chat:
            result = await server.extract_claims("content")
        self.assertEqual(result, ["A claim", "B claim"])
        self.assertEqual(chat.await_count, 3)

        with patch(
            "server.chat_with_retry",
            AsyncMock(return_value={"answers": ["raw failure"]}),
        ):
            with self.assertRaises(server.AgentJSONError) as raised:
                await server.ask_rocketride_json("prompt", "claim extraction")
        self.assertEqual(raised.exception.raw, "raw failure")

    async def test_every_claim_gets_both_linkup_searches(self):
        async def search(claim, direction):
            return {"claim": claim, "summary": direction, "sources": [{"url": direction}]}

        with (
            patch("server.extract_claims", AsyncMock(return_value=["one", "two"])),
            patch("server.search_linkup", AsyncMock(side_effect=search)) as linkup,
            patch(
                "server.synthesize_verdict",
                AsyncMock(return_value={"verdict": "mixed", "decision_summary": "summary"}),
            ),
        ):
            result = await server.run_factcheck("content")

        self.assertEqual(linkup.await_count, 4)
        self.assertEqual(
            {(call.args[0], call.args[1]) for call in linkup.await_args_list},
            {("one", "for"), ("one", "against"), ("two", "for"), ("two", "against")},
        )
        self.assertEqual(result["evidence_for"][0]["sources"], [{"url": "for"}])

    async def test_job_error_surfaces_truncated_raw_answer(self):
        job_id = "test-job"
        server.state["jobs"][job_id] = {}
        server.state["db"] = object()
        scraped = server.scraper.ScrapeResult("instagram", "content", None, {})

        with (
            patch("server.scraper.scrape", AsyncMock(return_value=scraped)),
            patch(
                "server.run_factcheck",
                AsyncMock(side_effect=server.AgentJSONError("claim extraction", "x" * 1200)),
            ),
        ):
            await server.process_factcheck(job_id, "url", "normalized")

        self.assertEqual(server.state["jobs"][job_id]["phase"], "error")
        self.assertEqual(len(server.state["jobs"][job_id]["raw"]), 1000)


class TikTokScraperTests(unittest.IsolatedAsyncioTestCase):
    async def test_tiktok_actor_payload_and_vtt_cleanup(self):
        item = {
            "id": "123",
            "success": True,
            "transcript": (
                "WEBVTT\n\n00:00:00.380 --> 00:00:03.600\nFirst claim.\n\n"
                "00:00:03.700 --> 00:00:06.760\nSecond claim."
            ),
        }
        with patch("scraper._run_apify_actor", AsyncMock(return_value=item)) as actor:
            result = await server.scraper.scrape("https://www.tiktok.com/@user/video/123")

        actor.assert_awaited_once_with(
            "scrape-creators~best-tiktok-transcripts-scraper",
            {"videos": ["https://www.tiktok.com/@user/video/123"]},
        )
        self.assertEqual(result.platform, "tiktok")
        self.assertEqual(result.content, "Spoken transcript:\nFirst claim.\n\nSecond claim.")
        self.assertIsNone(result.no_content_reason)


class XScraperTests(unittest.IsolatedAsyncioTestCase):
    async def test_x_actor_combines_post_text_and_transcript(self):
        item = {"title": "Post claim.", "text": "Spoken claim.", "errMsg": ""}
        with patch("scraper._run_apify_actor", AsyncMock(return_value=item)) as actor:
            result = await server.scraper.scrape("https://x.com/user/status/123")

        actor.assert_awaited_once_with(
            "apple_yang~twitter-video-transcript-api",
            {"videoUrl": "https://x.com/user/status/123"},
        )
        self.assertEqual(result.platform, "x")
        self.assertEqual(result.content, "Post text:\nPost claim.\n\nSpoken transcript:\nSpoken claim.")

    async def test_x_keeps_post_text_when_audio_is_unavailable(self):
        item = {"title": "Post claim.", "text": "", "errMsg": "no audio url found"}
        with patch("scraper._run_apify_actor", AsyncMock(return_value=item)):
            result = await server.scraper.scrape("https://twitter.com/user/status/123")

        self.assertEqual(result.content, "Post text:\nPost claim.")
        self.assertIsNone(result.no_content_reason)


class YouTubeScraperTests(unittest.IsolatedAsyncioTestCase):
    async def test_youtube_actor_payload_and_content(self):
        item = {
            "status": "success",
            "title": "Video title",
            "description": "Video description",
            "transcript_text": "Spoken claim.",
        }
        with patch("scraper._run_apify_actor", AsyncMock(return_value=item)) as actor:
            result = await server.scraper.scrape("https://youtu.be/abc123")

        actor.assert_awaited_once_with(
            "starvibe~youtube-video-transcript",
            {
                "youtube_url": "https://youtu.be/abc123",
                "language": "en",
                "include_transcript_text": True,
            },
        )
        self.assertEqual(result.platform, "youtube")
        self.assertEqual(
            result.content,
            "Video title:\nVideo title\n\nVideo description:\nVideo description\n\n"
            "Spoken transcript:\nSpoken claim.",
        )


if __name__ == "__main__":
    unittest.main()
