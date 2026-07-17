import unittest
from unittest.mock import AsyncMock, patch

import server


class FactCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_json_retries_and_keeps_last_raw_answer(self):
        responses = [
            {"answers": ["not json"]},
            {"answers": ["still not json"]},
            {"answers": ['{"claims": ["A claim"]}']},
        ]
        with patch("server.chat_with_retry", AsyncMock(side_effect=responses)) as chat:
            result = await server.ask_rocketride_json("prompt", "claim extraction")
        self.assertEqual(result, {"claims": ["A claim"]})
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


if __name__ == "__main__":
    unittest.main()
