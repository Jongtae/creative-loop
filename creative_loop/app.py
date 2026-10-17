from __future__ import annotations

import csv
import io
import json
import os
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from dotenv import load_dotenv
from .models import Brief, GenerateRequest, DesignSpec, EditRequest, Observation, Preference, AIRequest, VisionRequest, ImageRequest, now
from .store import Store
from .features import extract_image, redact_comment, event_rates, evidence_for, score_design, vector, best_ink
from .design import generate_specs, render_svg
from . import providers

ROOT = Path(__file__).parent
load_dotenv()


def uid():
    return uuid.uuid4().hex


def create_app(data_dir=None):
    store = Store(Path(data_dir or os.getenv("DATA_DIR", "data")))
    app = FastAPI(title="Creative Loop API", version="0.1.0", docs_url=None, redoc_url=None)
    app.state.store = store

    @app.middleware("http")
    async def local_guard(request: Request, call_next):
        allowed = set(os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver,::1").split(","))
        if request.url.hostname not in allowed:
            return JSONResponse({"detail": "허용되지 않은 Host입니다. 원격 공개 전에 인증·호스트 설정이 필요합니다."}, status_code=400)
        token = os.getenv("APP_TOKEN")
        if token and request.url.path.startswith("/api/"):
            import secrets
            supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
            if not secrets.compare_digest(supplied, token):
                return JSONResponse({"detail": "인증이 필요합니다."}, status_code=401)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("X-Creative-Loop") != "1":
                return JSONResponse({"detail": "X-Creative-Loop: 1 헤더가 필요합니다."}, status_code=403)
            origin = request.headers.get("Origin")
            if origin and urlparse(origin).netloc != request.url.netloc:
                return JSONResponse({"detail": "다른 출처에서의 쓰기는 차단됩니다."}, status_code=403)
            limit = 12 * 1024 * 1024
            try:
                announced_size = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "잘못된 Content-Length입니다."}, status_code=400)
            if announced_size > limit:
                return JSONResponse({"detail": "요청 크기는 12MB 이하이어야 합니다."}, status_code=413)
            chunks, length = [], 0
            async for chunk in request.stream():
                length += len(chunk)
                if length > limit:
                    return JSONResponse({"detail": "요청 크기는 12MB 이하이어야 합니다."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(providers.ProviderError)
    async def provider_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=502)

    def asset_bytes(asset_id, for_generation=False):
        if not asset_id:
            return None
        asset = store.get_asset(asset_id)
        if not asset:
            raise HTTPException(404, "이미지가 없습니다.")
        if for_generation and not asset["rights"].get("allow_generation"):
            raise HTTPException(403, "이 이미지의 재사용/생성 권한이 확인되지 않았습니다.")
        return (store.root / "assets" / f"{asset_id}.png").read_bytes()

    def design_or_404(design_id):
        design = store.get_design(design_id)
        if not design:
            raise HTTPException(404, "시안이 없습니다.")
        return design

    def enrich(design):
        category = design["brief"]["category"]
        design["scores"] = score_design(design, store.preferences(category))
        design["svg_url"] = f'/api/designs/{design["id"]}/svg?revision={design["revision"]}'
        design["evidence"] = evidence_for(design["spec"], store.observations(), design["context"])
        return design

    @app.get("/api/health")
    def health():
        with store.connect() as db:
            counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("assets", "observations", "designs", "preferences", "batches")}
        return {"status": "ok", "version": "0.1.0", "counts": counts,
                "capabilities": {"local_generation": True, "semantic_vision": providers.configured(),
                                 "ai_art_direction": providers.configured(), "ai_images": providers.image_configured(), "sns_auto_collection": False,
                                 "customer_preference_prediction": False},
                "model": os.getenv("OPENAI_MODEL") if providers.configured() else None}

    @app.post("/api/assets", status_code=201)
    async def upload(file: UploadFile = File(...), rights_basis: str = Form(...),
                     allow_generation: bool = Form(False), allow_model_input: bool = Form(False)):
        if not 3 <= len(rights_basis) <= 400:
            raise HTTPException(422, "사용권 근거를 3~400자로 입력하세요.")
        data = await file.read(10*1024*1024+1)
        try:
            clean, digest, features = extract_image(data)
        except Exception as exc:
            raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else "유효한 정지 이미지를 업로드하세요.") from None
        asset_id = uid()
        rights = {"basis": rights_basis, "allow_analysis": True, "allow_generation": allow_generation,
                  "allow_model_input": allow_model_input}
        (store.root / "assets" / f"{asset_id}.png").write_bytes(clean)
        with store.connect() as db:
            db.execute("INSERT INTO assets VALUES(?,?,?,?,?)", (asset_id, digest, json.dumps(features), json.dumps(rights), now()))
        return {"id": asset_id, "features": features, "rights": rights, "url": f"/api/assets/{asset_id}/image"}

    @app.get("/api/assets")
    def list_assets():
        with store.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM assets ORDER BY created_at DESC")]
        return [store.get_asset(a) for a in ids]

    @app.get("/api/assets/{asset_id}/image")
    def get_image(asset_id: str):
        return Response(asset_bytes(asset_id), media_type="image/png")

    @app.delete("/api/assets/{asset_id}")
    def remove_asset(asset_id: str):
        if not store.get_asset(asset_id):
            raise HTTPException(404, "이미지가 없습니다.")
        with store.connect() as db:
            in_use = any(db.execute(sql, (asset_id,)).fetchone() for sql in (
                "SELECT 1 FROM observations WHERE json_extract(payload,'$.asset_id')=? LIMIT 1",
                "SELECT 1 FROM designs WHERE json_extract(payload,'$.brief.asset_id')=? LIMIT 1",
                "SELECT 1 FROM revisions WHERE json_extract(payload,'$.brief.asset_id')=? LIMIT 1"))
        if in_use:
            raise HTTPException(409, "관측치·시안·이전 버전에서 사용 중입니다. 해당 관측치와 배치를 먼저 제거하세요.")
        with store.connect() as db:
            db.execute("DELETE FROM assets WHERE id=?", (asset_id,))
        (store.root / "assets" / f"{asset_id}.png").unlink(missing_ok=True)
        return {"deleted": asset_id}

    @app.get("/api/observations")
    def observations():
        return [{**r, "rates": event_rates(r)} for r in store.observations()]

    def ingest(raw):
        if not isinstance(raw, list) or not 1 <= len(raw) <= 500:
            raise HTTPException(422, "한 번에 1~500개 관측치를 배열로 가져오세요.")
        validated = []
        for n, item in enumerate(raw):
            try:
                obj = Observation.model_validate(item)
            except ValidationError as exc:
                errors = [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
                raise HTTPException(422, {"row": n+1, "errors": errors}) from None
            payload = obj.model_dump(mode="json")
            payload["comments"] = [redact_comment(c) for c in payload["comments"]]
            if obj.asset_id:
                asset = store.get_asset(obj.asset_id)
                if not asset:
                    raise HTTPException(422, f"{n+1}행: 존재하지 않는 asset_id입니다.")
                if not obj.palette:
                    payload["palette"] = asset["features"]["palette"]
                payload["pixel_features"] = asset["features"]
            validated.append(payload)
        inserted = 0
        with store.connect() as db:
            for item in validated:
                result = db.execute("INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?)",
                                    (uid(), item["platform"], item["source_id"], item["observed_at"], json.dumps(item, ensure_ascii=False)))
                inserted += result.rowcount
        return {"inserted": inserted, "duplicates": len(validated)-inserted, "validated": len(validated)}

    @app.post("/api/observations/import")
    async def import_json(request: Request):
        try:
            payload = await request.json()
        except ValueError:
            raise HTTPException(422, "올바른 JSON을 입력하세요.") from None
        return ingest(payload.get("observations") if isinstance(payload, dict) else payload)

    @app.post("/api/observations/import-file")
    async def import_file(file: UploadFile = File(...)):
        raw = await file.read(2*1024*1024+1)
        if len(raw) > 2*1024*1024:
            raise HTTPException(413, "가져오기 파일은 2MB 이하이어야 합니다.")
        try:
            text = raw.decode("utf-8-sig")
            if (file.filename or "").lower().endswith(".csv"):
                records = list(csv.DictReader(io.StringIO(text)))
                for row in records:
                    for k in list(row):
                        if row[k] == "":
                            row.pop(k)
                        elif k in {"palette", "tags", "comments"}:
                            row[k] = json.loads(row[k])
                        elif k in {"allow_analysis", "allow_generation", "allow_model_input", "is_demo"}:
                            if row[k].lower() not in {"true", "false", "1", "0"}:
                                raise ValueError("invalid boolean")
                            row[k] = row[k].lower() in {"true", "1"}
            else:
                records = json.loads(text)
                if isinstance(records, dict):
                    records = records.get("observations")
        except (ValueError, UnicodeDecodeError, AttributeError):
            raise HTTPException(422, "UTF-8 JSON 또는 CSV 형식을 확인하세요.") from None
        return ingest(records)

    @app.delete("/api/observations/{observation_id}")
    def delete_observation(observation_id: str):
        with store.connect() as db:
            found = db.execute("DELETE FROM observations WHERE id=?", (observation_id,)).rowcount
        if not found:
            raise HTTPException(404, "관측치가 없습니다.")
        return {"deleted": observation_id, "note": "독립적으로 업로드한 이미지는 자동 삭제되지 않습니다. 이미지 삭제 API를 별도로 사용하세요."}

    @app.post("/api/batches", status_code=201)
    def generate(request: GenerateRequest):
        asset_bytes(request.brief.asset_id, for_generation=True)
        specs, evidence_ids = generate_specs(request, store.observations())
        batch_id, created = uid(), now()
        context = request.model_dump(mode="json")
        designs = []
        with store.connect() as db:
            db.execute("INSERT INTO batches VALUES(?,?,?)", (batch_id, json.dumps(context, ensure_ascii=False), created))
            for index, spec in enumerate(specs):
                item = {"id": uid(), "batch_id": batch_id, "name": f"Variant {index+1:02d}",
                        "brief": request.brief.model_dump(), "spec": spec.model_dump(), "revision": 1,
                        "created_at": created, "context": context, "generation_evidence_ids": evidence_ids,
                        "engine": "deterministic-layout-v1", "selected": False}
                db.execute("INSERT INTO designs(id,batch_id,payload) VALUES(?,?,?)", (item["id"], batch_id, json.dumps(item, ensure_ascii=False)))
                designs.append(item)
        return {"batch_id": batch_id, "designs": [enrich(d) for d in designs], "generated": len(designs),
                "evidence_used": len(evidence_ids), "engine": "deterministic-layout-v1"}

    @app.get("/api/batches")
    def batches():
        with store.connect() as db:
            rows = db.execute("SELECT * FROM batches ORDER BY created_at DESC").fetchall()
        return [{"id": r["id"], "created_at": r["created_at"], "request": json.loads(r["request"])} for r in rows]

    @app.delete("/api/batches/{batch_id}")
    def delete_batch(batch_id: str):
        with store.connect() as db:
            if not db.execute("SELECT 1 FROM batches WHERE id=?", (batch_id,)).fetchone():
                raise HTTPException(404, "배치가 없습니다.")
            db.execute("DELETE FROM preferences WHERE winner_id IN (SELECT id FROM designs WHERE batch_id=?) OR loser_id IN (SELECT id FROM designs WHERE batch_id=?)", (batch_id, batch_id))
            db.execute("DELETE FROM revisions WHERE design_id IN (SELECT id FROM designs WHERE batch_id=?)", (batch_id,))
            db.execute("DELETE FROM designs WHERE batch_id=?", (batch_id,))
            db.execute("DELETE FROM batches WHERE id=?", (batch_id,))
        return {"deleted": batch_id, "note": "시안·편집 이력·이 배치의 선택 기록을 삭제했습니다. 원본 이미지는 별도 삭제합니다."}

    @app.get("/api/batches/{batch_id}/designs")
    def batch_designs(batch_id: str):
        return [enrich(d) for d in store.designs(batch_id)]

    @app.get("/api/designs/{design_id}")
    def get_design(design_id: str):
        return enrich(design_or_404(design_id))

    @app.get("/api/designs/{design_id}/svg")
    def svg(design_id: str):
        d = design_or_404(design_id)
        image = asset_bytes(d["brief"].get("asset_id"), for_generation=True)
        return Response(render_svg(Brief(**d["brief"]), DesignSpec(**d["spec"]), image), media_type="image/svg+xml",
                        headers={"Cache-Control": "no-store"})

    @app.put("/api/designs/{design_id}")
    def edit(design_id: str, request: EditRequest):
        d = design_or_404(design_id)
        asset_bytes(request.brief.asset_id, for_generation=True)
        if request.expected_revision != d["revision"]:
            raise HTTPException(409, "다른 편집이 먼저 저장됐습니다. 시안을 다시 열어주세요.")
        old = json.dumps(d, ensure_ascii=False)
        with store.connect() as db:
            # BEGIN IMMEDIATE serializes revision checks for concurrent writers.
            db.execute("BEGIN IMMEDIATE")
            fresh = json.loads(db.execute("SELECT payload FROM designs WHERE id=?", (design_id,)).fetchone()[0])
            if fresh["revision"] != request.expected_revision:
                raise HTTPException(409, "편집 충돌입니다. 최신 시안을 다시 여세요.")
            db.execute("INSERT INTO revisions(design_id,revision,payload,created_at) VALUES(?,?,?,?)", (design_id, d["revision"], old, now()))
            d.update(brief=request.brief.model_dump(), spec=request.spec.model_dump(), revision=d["revision"]+1)
            db.execute("UPDATE designs SET payload=? WHERE id=?", (json.dumps(d, ensure_ascii=False), design_id))
        return enrich(d)

    @app.post("/api/designs/{design_id}/fix-contrast")
    def fix_contrast(design_id: str):
        d = design_or_404(design_id)
        d["spec"]["foreground"] = best_ink(d["spec"]["background"])
        return edit(design_id, EditRequest(brief=d["brief"], spec=d["spec"], expected_revision=d["revision"]))

    @app.get("/api/designs/{design_id}/revisions")
    def revisions(design_id: str):
        design_or_404(design_id)
        with store.connect() as db:
            rows = db.execute("SELECT revision,payload,created_at FROM revisions WHERE design_id=? ORDER BY revision DESC", (design_id,)).fetchall()
        return [{"revision": r["revision"], "created_at": r["created_at"], "design": json.loads(r["payload"])} for r in rows]

    @app.post("/api/designs/{design_id}/select")
    def select(design_id: str):
        d = design_or_404(design_id)
        with store.connect() as db:
            db.execute("UPDATE designs SET selected=? WHERE id=?", (not d["selected"], design_id))
        return enrich(store.get_design(design_id))

    @app.post("/api/preferences", status_code=201)
    def preference(request: Preference):
        winner, loser = design_or_404(request.winner_id), design_or_404(request.loser_id)
        if winner["batch_id"] != loser["batch_id"]:
            raise HTTPException(422, "동일한 브리프의 같은 배치 시안끼리 비교하세요.")
        payload = {**request.model_dump(), "category": winner["brief"]["category"],
                   "winner_vector": vector(winner["spec"]).tolist(), "loser_vector": vector(loser["spec"]).tolist(),
                   "winner_revision": winner["revision"], "loser_revision": loser["revision"],
                   "source": "local_designer_choice"}
        with store.connect() as db:
            db.execute("INSERT INTO preferences VALUES(?,?,?,?,?)", (uid(), request.winner_id, request.loser_id,
                        json.dumps(payload, ensure_ascii=False), now(),))
        return {"recorded": True}

    @app.get("/api/batches/{batch_id}/export")
    def export(batch_id: str, selected_only: bool = False):
        designs = store.designs(batch_id)
        if selected_only:
            designs = [d for d in designs if d["selected"]]
        if not designs:
            raise HTTPException(404, "내보낼 시안이 없습니다.")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for d in designs:
                name = d["id"]
                archive.writestr(f"{name}.svg", render_svg(Brief(**d["brief"]), DesignSpec(**d["spec"]), asset_bytes(d["brief"].get("asset_id"), True)))
                archive.writestr(f"{name}.json", json.dumps(enrich(d), ensure_ascii=False, indent=2))
            archive.writestr("README.txt", "Creative Loop export: editable SVG + design spec JSON. Fonts are not embedded.\nScores are heuristic checks / local designer choices, not consumer preference predictions.\n")
        return Response(output.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="creative-loop-designs.zip"'})

    @app.post("/api/ai/art-direction")
    def ai_direction(request: AIRequest):
        if not request.confirm_external_processing:
            raise HTTPException(403, "브리프를 외부 AI로 보내는 데 동의가 필요합니다.")
        return providers.art_direction(store, request.brief, request.instruction)

    @app.post("/api/ai/vision")
    def ai_vision(request: VisionRequest):
        asset = store.get_asset(request.asset_id)
        if not asset:
            raise HTTPException(404, "이미지가 없습니다.")
        if not request.confirm_external_processing or not asset["rights"].get("allow_model_input"):
            raise HTTPException(403, "이미지의 외부 AI 입력 권한과 전송 동의가 필요합니다.")
        analysis = providers.describe_image(store, asset_bytes(request.asset_id))
        asset["features"]["semantic_analysis"] = analysis
        with store.connect() as db:
            db.execute("UPDATE assets SET features=? WHERE id=?", (json.dumps(asset["features"], ensure_ascii=False), request.asset_id))
        return analysis

    @app.post("/api/ai/images", status_code=201)
    def ai_image(request: ImageRequest):
        if not request.confirm_external_processing:
            raise HTTPException(403, "외부 AI 전송과 유료 이미지 호출에 대한 동의가 필요합니다.")
        source = None
        if request.asset_id:
            asset = store.get_asset(request.asset_id)
            if not asset:
                raise HTTPException(404, "수정할 이미지가 없습니다. 먼저 업로드하세요.")
            if not asset["rights"].get("allow_model_input") or not asset["rights"].get("allow_generation"):
                raise HTTPException(403, "원본 이미지의 AI 입력 권한과 수정·재사용 권한이 필요합니다.")
            source = asset_bytes(request.asset_id, for_generation=True)
        clean, digest, features, provenance = providers.image_create_or_edit(store, request, source)
        asset_id = uid()
        features["generation"] = provenance
        rights = {"basis": "외부 AI 생성 초안; 게시 전 사용권과 내용을 검토해야 합니다.",
                  "allow_analysis": True, "allow_generation": True, "allow_model_input": True}
        (store.root / "assets" / f"{asset_id}.png").write_bytes(clean)
        with store.connect() as db:
            db.execute("INSERT INTO assets VALUES(?,?,?,?,?)", (asset_id, digest, json.dumps(features, ensure_ascii=False),
                       json.dumps(rights, ensure_ascii=False), now()))
        return {"id": asset_id, "features": features, "rights": rights, "url": f"/api/assets/{asset_id}/image",
                "note": "새 이미지로 저장했습니다. 작업실에서 선택해 레이아웃 시안을 생성하세요. 원본은 변경하지 않았습니다."}

    @app.get("/api/example")
    def example():
        return FileResponse(ROOT.parent / "examples" / "demo-observations.json", media_type="application/json", filename="demo-observations.json")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    return app


app = create_app()
