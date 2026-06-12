from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class PassBidWritingMcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        os.environ["PASS_BID_WRITING_STORAGE_DIR"] = str(Path(self.tempdir.name) / "storage")

    def test_case_ingest_matrix_docx_and_check(self) -> None:
        from pass_bid_writing import mcp_server

        root = Path(self.tempdir.name)
        tender = root / "tender.md"
        bid = root / "passed.md"
        tender.write_text(
            "\n".join(
                [
                    "本项目技术标采用通过制，投标文件应实质性响应招标文件要求。",
                    "施工组织设计应包含工期、质量、安全文明施工、环境保护、资源配置。",
                    "项目涉及河道治理、围堰导流、度汛和排水措施。",
                ]
            ),
            encoding="utf-8",
        )
        bid.write_text(
            "\n".join(
                [
                    "一、编制说明及工程概况",
                    "本技术标完全响应招标文件要求。",
                    "二、施工进度计划及保证措施",
                    "合理安排工期节点。",
                    "三、河道治理、围堰导流及度汛措施",
                    "设置围堰导流和排水体系，确保安全度汛。",
                ]
            ),
            encoding="utf-8",
        )

        ingested = mcp_server.writing_ingest_case_pair(
            tender_file=str(tender),
            bid_file=str(bid),
            title="河道治理通过制案例",
            project_type="河道治理",
            tags="water,pass",
        )
        self.assertGreaterEqual(ingested["summary"]["requirement_count"], 2)

        requirements = mcp_server.writing_extract_tender_requirements(tender_file=str(tender))
        matrix = mcp_server.writing_build_response_matrix(requirements=requirements)["matrix"]
        self.assertGreaterEqual(len(matrix), 2)

        outline = mcp_server.writing_generate_outline(
            requirements=requirements,
            project_type="河道治理",
        )["outline"]
        docx = mcp_server.writing_generate_docx(
            title="测试项目通过制技术标",
            outline=outline,
            requirements=requirements,
            response_matrix=matrix,
            output_name="test-draft",
            tender_path=str(tender),
        )
        self.assertTrue(Path(docx["docx_path"]).exists())

        compliance = mcp_server.writing_check_draft_compliance(
            draft_docx=docx["docx_path"],
            requirements=requirements,
        )
        self.assertIn("status", compliance)


if __name__ == "__main__":
    unittest.main()
