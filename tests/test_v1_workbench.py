from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from docx import Document
from docx.enum.section import WD_ORIENT
from PIL import Image

from pass_bid_writing import db
from pass_bid_writing.config import get_settings
from pass_bid_writing.drawings import build_drawing_registry
from pass_bid_writing.documents import generate_docx
from pass_bid_writing.knowledge import load_case_assets


class DrawingRegistryTests(unittest.TestCase):
    def test_dwg_without_pdf_is_explicitly_blocked(self) -> None:
        drawings, confirmations = build_drawing_registry(
            [{"name": "泵站总平面图.dwg", "path": "C:/x/泵站总平面图.dwg", "suffix": ".dwg", "role": "drawing"}]
        )
        self.assertEqual(drawings[0]["status"], "missing_pdf")
        self.assertEqual(confirmations[0]["category"], "图纸待转换")
        self.assertEqual(confirmations[0]["severity"], "high")

    def test_similar_dwg_and_pdf_are_paired(self) -> None:
        drawings, confirmations = build_drawing_registry(
            [
                {"name": "河道施工总平图.dwg", "path": "C:/x/河道施工总平图.dwg", "suffix": ".dwg", "role": "drawing"},
                {"name": "河道施工总平图.pdf", "path": "C:/x/河道施工总平图.pdf", "suffix": ".pdf", "role": "drawing"},
            ]
        )
        self.assertFalse(confirmations)
        self.assertEqual(drawings[0]["source_pdf_path"], "C:/x/河道施工总平图.pdf")


class DocumentAssemblyTests(unittest.TestCase):
    def test_a4_tables_and_landscape_drawing_are_native_word_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "drawing.png"
            Image.new("RGB", (1600, 1000), "white").save(image)
            output = root / "draft.docx"
            previous = os.environ.get("PASS_BID_WRITING_DISABLE_WORD_COM")
            os.environ["PASS_BID_WRITING_DISABLE_WORD_COM"] = "1"
            try:
                generate_docx(
                    title="测试工程施工组织设计",
                    output_path=output,
                    sections=[
                        {
                            "title": "施工总平面布置",
                            "content": (
                                "| 控制项 | 执行要求 |\n|---|---|\n| 图纸 | 人工确认 |\n\n"
                                f"![图4-1 总平面布置图|landscape]({image})"
                            ),
                        }
                    ],
                )
            finally:
                if previous is None:
                    os.environ.pop("PASS_BID_WRITING_DISABLE_WORD_COM", None)
                else:
                    os.environ["PASS_BID_WRITING_DISABLE_WORD_COM"] = previous
            document = Document(output)
            self.assertAlmostEqual(document.sections[0].page_width.inches, 8.27, places=1)
            self.assertGreaterEqual(len(document.sections), 3)
            self.assertEqual(document.sections[1].orientation, WD_ORIENT.LANDSCAPE)
            self.assertEqual(document.sections[-1].orientation, WD_ORIENT.PORTRAIT)
            header_xml = document.tables[0].rows[0]._tr.xml
            self.assertIn("tblHeader", header_xml)
            self.assertIn("cantSplit", header_xml)


class WorkbenchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get("PASS_BID_DATA_DIR")
        os.environ["PASS_BID_DATA_DIR"] = str(Path(self.temp.name) / "data")
        import pass_bid_writing.api as api_module

        importlib.reload(api_module)
        self.client = TestClient(api_module.create_app())

    def tearDown(self) -> None:
        if self.previous is None:
            os.environ.pop("PASS_BID_DATA_DIR", None)
        else:
            os.environ["PASS_BID_DATA_DIR"] = self.previous
        self.temp.cleanup()

    def test_folder_import_preserves_relative_path_and_runs_analysis(self) -> None:
        response = self.client.post(
            "/api/projects/import",
            data={
                "project_name": "E2E项目",
                "project_type": "河道治理工程",
                "relative_paths": ["资料夹/招标文件.txt", "资料夹/初设/初步设计报告.txt"],
            },
            files=[
                ("files", ("招标文件.txt", b"project name: E2E", "text/plain")),
                ("files", ("初步设计报告.txt", b"design report", "text/plain")),
            ],
        )
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["job"]["id"]
        job = self.client.get(f"/api/jobs/{job_id}").json()
        self.assertEqual(job["job"]["status"], "succeeded")
        state = job["state"]
        self.assertTrue(state["run_id"])
        paths = [Path(item["path"]) for item in state["files"]]
        self.assertTrue(any("初设" in str(path) for path in paths))

    def test_folder_import_rejects_parent_traversal(self) -> None:
        response = self.client.post(
            "/api/projects/import",
            data={
                "project_name": "不安全路径",
                "project_type": "水利工程通用",
                "relative_paths": ["../outside.txt"],
            },
            files=[("files", ("outside.txt", b"x", "text/plain"))],
        )
        self.assertEqual(response.status_code, 400)

    def test_model_config_is_written_outside_repository(self) -> None:
        response = self.client.patch(
            "/api/config",
            json={"deepseek_model": "deepseek-test-model"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        config_path = Path(response.json()["config_path"])
        self.assertTrue(config_path.exists())
        self.assertIn(str(Path(self.temp.name) / "data"), str(config_path))
        self.assertIn("PASS_BID_TEXT_MODEL", config_path.read_text(encoding="utf-8"))

    def test_case_distillation_can_be_inspected_corrected_and_disabled(self) -> None:
        settings = get_settings()
        with db.db_session(settings.database_path) as conn:
            case_id = db.create_case_pair(
                conn,
                title="待审核案例",
                project_type="河道治理工程",
                region="浙江",
                tags="河道,通过制",
                tender_path="招标文件.pdf",
                bid_path="已通过技术标.docx",
                tender_text="招标要求",
                bid_text="第一章 施工部署",
                outline=[{"level": 1, "title": "施工部署", "order": 1}],
                requirements={},
                patterns={
                    "outline": [{"level": 1, "title": "施工部署", "order": 1}],
                    "scene_terms": ["围堰"],
                    "reusable_snippets": [{"keyword": "部署", "text": "按区段组织施工。"}],
                    "style_notes": ["先响应要求再展开措施。"],
                },
            )
        detail = self.client.get(f"/api/cases/{case_id}")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["scene_terms"], ["围堰"])
        saved = self.client.patch(
            f"/api/cases/{case_id}",
            json={
                "outline": [
                    {"level": 1, "title": "施工总体部署"},
                    {"level": 1, "title": "主要施工方案"},
                ],
                "scene_terms": ["围堰", "导流"],
                "reusable_snippets": [{"keyword": "导流", "text": "结合项目图纸确定导流顺序。"}],
                "style_notes": ["逐项响应招标要求。"],
                "enabled": False,
                "review_status": "confirmed",
                "review_notes": "人工已修正目录。",
            },
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        payload = saved.json()
        self.assertFalse(payload["enabled"])
        self.assertEqual(len(payload["outline"]), 2)
        self.assertEqual(payload["review_notes"], "人工已修正目录。")
        listing = self.client.get("/api/cases").json()
        self.assertFalse(listing[0]["enabled"])
        self.assertEqual(
            load_case_assets(project_type="河道治理工程", requirement_text="围堰导流"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
