from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PassBidWritingMcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        os.environ["PASS_BID_WRITING_STORAGE_DIR"] = str(Path(self.tempdir.name) / "storage")
        self._restore_env = {}
        for key in (
            "PASS_BID_PROJECTS_DIR",
            "PASS_BID_VISION_API_KEY",
            "DASHSCOPE_API_KEY",
            "MOONSHOT_API_KEY",
            "ARK_API_KEY",
            "VOLCENGINE_API_KEY",
            "PASS_BID_VISION_BASE_URL",
        ):
            self._restore_env[key] = os.environ.get(key)
            os.environ.pop(key, None)
        self.addCleanup(self._restore_environment)

    def _restore_environment(self) -> None:
        for key, value in self._restore_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

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
            visual_qa=False,
        )
        self.assertTrue(Path(docx["docx_path"]).exists())

        compliance = mcp_server.writing_check_draft_compliance(
            draft_docx=docx["docx_path"],
            requirements=requirements,
        )
        self.assertIn("status", compliance)

    def test_project_folder_aliases_and_new_tender_prepare(self) -> None:
        from pass_bid_writing import mcp_server

        root = Path(self.tempdir.name)
        projects = root / "projects"
        passed = projects / "passed" / "河道治理已通过"
        unpassed = projects / "unpassed" / "新河道项目"
        passed.mkdir(parents=True)
        unpassed.mkdir(parents=True)
        (passed / "招标文件.md").write_text(
            "本项目技术标采用通过制，应包含工期、质量、安全文明施工和环境保护。",
            encoding="utf-8",
        )
        (passed / "已通过技术标.md").write_text(
            "\n".join(
                [
                    "一、编制说明及工程概况",
                    "本技术标完全响应招标文件。",
                    "二、围堰导流及度汛措施",
                    "设置围堰导流和排水体系。",
                ]
            ),
            encoding="utf-8",
        )
        (unpassed / "招标文件.md").write_text(
            "通过制技术标应响应工期、质量、安全、环保、河道治理和度汛要求。",
            encoding="utf-8",
        )

        scanned = mcp_server.writing_scan_projects(root=str(projects))
        self.assertEqual(scanned["passed_case_count"], 1)
        self.assertEqual(scanned["new_tender_count"], 1)
        self.assertTrue(scanned["passed_cases"][0]["ready"])
        self.assertTrue(scanned["new_tenders"][0]["ready"])

        ingested = mcp_server.writing_ingest_passed_case(
            project_dir=str(passed),
            auto_visual=False,
        )
        self.assertGreaterEqual(ingested["summary"]["outline_count"], 2)
        self.assertIsNone(ingested["layout_profile"])

        prepared = mcp_server.writing_prepare_new_tender(
            project_dir=str(unpassed),
            auto_visual=False,
        )
        self.assertGreaterEqual(prepared["requirements"]["requirement_count"], 1)
        self.assertGreaterEqual(len(prepared["response_matrix"]), 1)
        self.assertTrue(prepared["outputs_dir"].endswith("outputs"))

    def test_layout_profile_without_api_key_renders_and_degrades(self) -> None:
        from pass_bid_writing import mcp_server

        pdf = Path(self.tempdir.name) / "layout-sample.pdf"
        self._write_sample_pdf(pdf)

        result = mcp_server.writing_extract_layout_profile(
            file_path=str(pdf),
            source_kind="accepted_bid",
        )
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["render"]["status"], "ready")
        self.assertTrue(result["layout_profile_id"])
        self.assertTrue(Path(result["render"]["pages"][0]["image_path"]).exists())

    def test_layout_profile_parses_mock_vision_json(self) -> None:
        from pass_bid_writing import mcp_server

        os.environ["PASS_BID_VISION_API_KEY"] = "test-key"
        os.environ["PASS_BID_VISION_BASE_URL"] = "https://example.test/v1"
        pdf = Path(self.tempdir.name) / "mock-vision.pdf"
        self._write_sample_pdf(pdf)

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json_bytes(
                    '{"choices":[{"message":{"content":"{\\"cover\\":{\\"subtitle\\":\\"技术标\\"},'
                    '\\"heading_hierarchy\\":[\\"一级标题居中\\"],\\"visual_findings\\":[]}"}}]}'
                )

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = mcp_server.writing_extract_layout_profile(
                file_path=str(pdf),
                source_kind="accepted_bid",
            )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["profile"]["cover"]["subtitle"], "技术标")
        self.assertTrue(result["layout_profile_id"])

    def _write_sample_pdf(self, path: Path) -> None:
        import fitz  # type: ignore

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Pass bid technical document layout sample")
        page.insert_text((72, 110), "Cover / TOC / heading / footer visual test")
        doc.save(str(path))
        doc.close()


def json_bytes(value: str) -> bytes:
    return value.encode("utf-8")


if __name__ == "__main__":
    unittest.main()
