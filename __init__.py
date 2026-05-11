from .nodes.pose_studio import AdvancedPoseStudio

ADVANCED_POSE_STUDIO_NODE_ID = "Advanced_Pose_Studio"
ADVANCED_POSE_STUDIO_DISPLAY_NAME = "Advanced Pose Studio"

NODE_CLASS_MAPPINGS = {
    ADVANCED_POSE_STUDIO_NODE_ID: AdvancedPoseStudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    ADVANCED_POSE_STUDIO_NODE_ID: ADVANCED_POSE_STUDIO_DISPLAY_NAME,
}

WEB_DIRECTORY = "./web"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]


# === API Endpoint Registration for Pose Studio ===
import os
import numpy as np
import threading

def _advanced_pose_register_endpoint():
    """Lazy registration to avoid import errors in analysis tools."""
    try:
        from server import PromptServer
        from aiohttp import web
    except Exception:
        return

    @PromptServer.instance.routes.post("/advanced_pose_studio/character/update_preview")
    async def advanced_pose_character_update_preview(request):
        try:
            data = await request.json()
            
            # Extract params
            age = float(data.get('age', 25.0))
            gender = float(data.get('gender', 0.5))
            weight = float(data.get('weight', 0.5))
            muscle = float(data.get('muscle', 0.5))
            height = float(data.get('height', 0.5))
            breast_size = float(data.get('breast_size', 0.5))
            breast_size = float(data.get('breast_size', 0.5))
            firmness = float(data.get('firmness', 0.5))
            penis_len = float(data.get('penis_len', 0.5))
            penis_circ = float(data.get('penis_circ', 0.5))
            penis_test = float(data.get('penis_test', 0.5))
            
            # Import from CharacterData
            from .CharacterData.mh_parser import HumanSolver
            from .CharacterData import matrix
            from .nodes.pose_studio import POSE_STUDIO_CACHE, _ensure_data_loaded
            
            # Normalize age
            mh_age = (age - 1.0) / (90.0 - 1.0)
            mh_age = max(0.0, min(1.0, mh_age))
            
            # Ensure data loaded
            _ensure_data_loaded()
            
            # Solve mesh
            solver = HumanSolver()
            factors = solver.calculate_factors(mh_age, gender, weight, muscle, height, breast_size, firmness, penis_len, penis_circ, penis_test)
            new_verts = solver.solve_mesh(POSE_STUDIO_CACHE['base_mesh'], POSE_STUDIO_CACHE['targets'], factors)
            
            # Get skeleton
            skel = POSE_STUDIO_CACHE.get('skeleton')
            
            # Filter faces and return
            base_mesh = POSE_STUDIO_CACHE['base_mesh']
            valid_prefixes = ["body", "helper-r-eye", "helper-l-eye", "helper-upper-teeth", "helper-lower-teeth", "helper-tongue", "helper-genital"]
            
            valid_faces = []
            if base_mesh.face_groups:
                for i, group in enumerate(base_mesh.face_groups):
                    g_clean = group.strip()
                    is_valid = g_clean in valid_prefixes
                    if g_clean.startswith("joint-"): is_valid = False
                    if g_clean in ["helper-skirt", "helper-tights", "helper-hair"]: is_valid = False
                    if g_clean == "helper-genital" and gender < 0.99: is_valid = False
                    
                    if is_valid:
                        valid_faces.append(base_mesh.faces[i])
            
            # Convert quads to triangles
            tri_indices = []
            for face in valid_faces:
                v_indices = []
                for item in face:
                    if isinstance(item, (list, tuple)):
                        v_indices.append(item[0])
                    else:
                        v_indices.append(item)
                
                if len(v_indices) == 3:
                    tri_indices.extend([v_indices[0], v_indices[1], v_indices[2]])
                elif len(v_indices) == 4:
                    tri_indices.extend([v_indices[0], v_indices[1], v_indices[2]])
                    tri_indices.extend([v_indices[0], v_indices[2], v_indices[3]])
            
            # Extract Bones Data
            bones_data = []
            weights_for_frontend = {}
            
            if skel:
                class MeshWrapper:
                    def __init__(self, verts):
                        self.vertices = verts
                mesh_wrapper = MeshWrapper(new_verts)
                skel.updateJointPositions(mesh_wrapper)

                for bone in skel.getBones():
                    headPos = bone.headPos.tolist() if hasattr(bone.headPos, 'tolist') else list(bone.headPos)
                    tailPos = bone.tailPos.tolist() if hasattr(bone.tailPos, 'tolist') else list(bone.tailPos)
                    
                    restMatrix = None
                    if bone.matRestGlobal is not None:
                        restMatrix = bone.matRestGlobal.flatten().tolist()
                    
                    bones_data.append({
                        "name": bone.name,
                        "headPos": headPos,
                        "tailPos": tailPos,
                        "parent": bone.parent.name if bone.parent else None,
                        "length": float(bone.length) if hasattr(bone, 'length') else 0.0,
                        "restMatrix": restMatrix
                    })
                
                # Prepare weights for frontend skinning
                if skel.vertexWeights:
                    for bone_name, (indices, w_vals) in skel.vertexWeights.data.items():
                        weights_for_frontend[bone_name] = {
                            "indices": indices.tolist() if hasattr(indices, 'tolist') else list(indices),
                            "weights": w_vals.tolist() if hasattr(w_vals, 'tolist') else list(w_vals)
                        }

            return web.json_response({
                "status": "success",
                "vertices": new_verts.flatten().tolist(),
                "uvs": base_mesh.vertex_uvs.flatten().tolist() if hasattr(base_mesh, 'vertex_uvs') else [],
                "indices": tri_indices,
                "normals": [],
                "bones": bones_data,
                "weights": weights_for_frontend
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return web.json_response({"error": str(e)}, status=500)

_advanced_pose_register_endpoint()

# Register Pose Library API
def _advanced_pose_register_pose_library():
    try:
        from server import PromptServer
        from .api.pose_library import register_routes
        register_routes(PromptServer.instance.app)
    except Exception as e:
        print(f"[Advanced] Failed to register Pose Library API: {e}")

_advanced_pose_register_pose_library()


# === Pose Studio Capture Cache ===
ADVANCED_POSE_CAPTURE_CACHE = {}
_CAPTURE_CACHE_MAX = 10

def _advanced_pose_register_capture_cache():
    try:
        from server import PromptServer
        from aiohttp import web
    except Exception:
        return

    @PromptServer.instance.routes.post("/advanced_pose_studio/pose_captures_upload")
    async def advanced_pose_captures_upload(request):
        try:
            data = await request.json()
            capture_id = data.get("capture_id")
            if not capture_id:
                return web.json_response({"error": "missing capture_id"}, status=400)

            ADVANCED_POSE_CAPTURE_CACHE[capture_id] = {
                "captured_images": data.get("captured_images", []),
                "lighting_prompts": data.get("lighting_prompts", []),
                "background_only": data.get("background_only"),
                "character_layers": data.get("character_layers", []),
            }

            # LRU eviction: keep only last _CAPTURE_CACHE_MAX entries
            while len(ADVANCED_POSE_CAPTURE_CACHE) > _CAPTURE_CACHE_MAX:
                oldest = next(iter(ADVANCED_POSE_CAPTURE_CACHE))
                del ADVANCED_POSE_CAPTURE_CACHE[oldest]

            return web.json_response({"status": "ok", "capture_id": capture_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @PromptServer.instance.routes.get("/advanced_pose_studio/pose_captures/{capture_id}")
    async def advanced_pose_captures_get(request):
        capture_id = request.match_info["capture_id"]
        entry = ADVANCED_POSE_CAPTURE_CACHE.get(capture_id)
        if not entry:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response(entry)

_advanced_pose_register_capture_cache()


def _decode_data_url_image(data_url):
    if not isinstance(data_url, str) or not data_url:
        raise ValueError("missing image")
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]

    import base64
    import io
    from PIL import Image

    raw = base64.b64decode(data_url)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _pil_to_comfy_image_tensor(image):
    import numpy as np
    import torch

    arr = np.asarray(image).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None,]


def _extract_openpose_payload(result):
    import json

    if isinstance(result, dict):
        result_tuple = result.get("result")
        if isinstance(result_tuple, (list, tuple)) and len(result_tuple) > 1 and result_tuple[1]:
            return result_tuple[1]

        ui = result.get("ui") or {}
        openpose_json = ui.get("openpose_json")
        if openpose_json:
            payload = openpose_json[0] if isinstance(openpose_json, list) else openpose_json
            return json.loads(payload) if isinstance(payload, str) else payload

    if isinstance(result, (list, tuple)) and len(result) > 1 and result[1]:
        return result[1]

    return None


def _extract_image_tensor_payload(result):
    if isinstance(result, dict):
        result_tuple = result.get("result")
        if isinstance(result_tuple, (list, tuple)) and len(result_tuple) > 0:
            return result_tuple[0]
    if isinstance(result, (list, tuple)) and len(result) > 0:
        return result[0]
    return result


def _run_node_with_prompt_context(fn):
    from server import PromptServer

    prompt_server = PromptServer.instance
    had_last_prompt_id = hasattr(prompt_server, "last_prompt_id")
    previous_last_prompt_id = getattr(prompt_server, "last_prompt_id", None)
    if not had_last_prompt_id:
        prompt_server.last_prompt_id = "advanced_pose_studio_initializer"
    try:
        return fn()
    finally:
        if had_last_prompt_id:
            prompt_server.last_prompt_id = previous_last_prompt_id
        else:
            try:
                delattr(prompt_server, "last_prompt_id")
            except AttributeError:
                pass


_ADVANCED_POSE_PREPROCESSOR_INSTALL_LOCK = threading.Lock()
_ADVANCED_POSE_PREPROCESSOR_INSTALL_ATTEMPTED = False
_ADVANCED_POSE_OPENPOSE_PROGRESS = {}
_ADVANCED_POSE_CONTROLNET_AUX_REPO = "https://github.com/Fannovel16/comfyui_controlnet_aux.git"
_ADVANCED_POSE_CONTROLNET_AUX_DIR = "comfyui_controlnet_aux"
_ADVANCED_POSE_VENDOR_CONTROLNET_AUX_DIR = os.path.join(os.path.dirname(__file__), "vendor", "comfyui_controlnet_aux")
_ADVANCED_POSE_DETECTOR_NODE_NAMES = {
    "DWPreprocessor",
    "OpenposePreprocessor",
    "AIO_Preprocessor",
}


def _custom_nodes_root():
    try:
        import folder_paths

        paths = folder_paths.get_folder_paths("custom_nodes")
        if paths:
            return paths[0]
    except Exception:
        pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _has_pose_preprocessor_mapping(mappings):
    return any(name in mappings for name in _ADVANCED_POSE_DETECTOR_NODE_NAMES)


def _controlnet_aux_requirements_missing():
    import importlib.util

    required_modules = [
        "cv2",
        "huggingface_hub",
        "matplotlib",
        "scipy",
        "skimage",
        "torchvision",
        "yaml",
    ]
    return [name for name in required_modules if importlib.util.find_spec(name) is None]


def _controlnet_aux_candidate_paths():
    candidates = []
    for path in [
        _ADVANCED_POSE_VENDOR_CONTROLNET_AUX_DIR,
        os.path.join(os.path.dirname(__file__), _ADVANCED_POSE_CONTROLNET_AUX_DIR),
        os.path.join(_custom_nodes_root(), _ADVANCED_POSE_CONTROLNET_AUX_DIR),
    ]:
        if path not in candidates:
            candidates.append(path)
    return candidates


def _update_openpose_progress(job_id, **kwargs):
    if not job_id:
        return
    import time

    state = _ADVANCED_POSE_OPENPOSE_PROGRESS.get(job_id, {})
    if "percent" not in kwargs:
        state.pop("percent", None)
    state.update(kwargs)
    state["updated_at"] = time.time()
    _ADVANCED_POSE_OPENPOSE_PROGRESS[job_id] = state

    now = time.time()
    for key, value in list(_ADVANCED_POSE_OPENPOSE_PROGRESS.items()):
        if now - value.get("updated_at", now) > 600:
            _ADVANCED_POSE_OPENPOSE_PROGRESS.pop(key, None)


def _install_openpose_progress_callback(job_id):
    if not job_id:
        return None
    import builtins

    previous = getattr(builtins, "ADVANCED_POSE_STUDIO_PROGRESS_CALLBACK", None)

    def _callback(message, stage="downloading_model", status="running", percent=None):
        payload = {
            "status": status,
            "stage": stage,
            "message": message,
        }
        if percent is not None:
            payload["percent"] = percent
        _update_openpose_progress(job_id, **payload)

    builtins.ADVANCED_POSE_STUDIO_PROGRESS_CALLBACK = _callback
    return previous


def _restore_openpose_progress_callback(previous):
    import builtins

    if previous is None:
        try:
            delattr(builtins, "ADVANCED_POSE_STUDIO_PROGRESS_CALLBACK")
        except AttributeError:
            pass
    else:
        builtins.ADVANCED_POSE_STUDIO_PROGRESS_CALLBACK = previous


def _install_controlnet_aux_custom_node(repo_path, job_id=None):
    import subprocess
    import sys
    import zipfile
    import tempfile
    import shutil
    import urllib.request

    if not os.path.isdir(repo_path):
        parent = os.path.dirname(repo_path)
        os.makedirs(parent, exist_ok=True)
        try:
            _update_openpose_progress(
                job_id,
                status="running",
                stage="installing_preprocessor",
                message="Installing DWPose/OpenPose preprocessors",
            )
            subprocess.run(
                ["git", "clone", "--depth", "1", _ADVANCED_POSE_CONTROLNET_AUX_REPO, repo_path],
                cwd=parent,
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            archive_url = "https://github.com/Fannovel16/comfyui_controlnet_aux/archive/refs/heads/main.zip"
            with tempfile.TemporaryDirectory(prefix="aps_controlnet_aux_") as tmp:
                zip_path = os.path.join(tmp, "comfyui_controlnet_aux.zip")
                req = urllib.request.Request(archive_url, headers={"User-Agent": "Advanced-Pose-Studio"})
                _update_openpose_progress(
                    job_id,
                    status="running",
                    stage="downloading_preprocessor",
                    message="Downloading DWPose/OpenPose preprocessors",
                )
                with urllib.request.urlopen(req, timeout=120) as response, open(zip_path, "wb") as f:
                    total = int(response.headers.get("Content-Length") or 0)
                    done = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            pct = round((done / total) * 100, 1)
                            _update_openpose_progress(
                                job_id,
                                status="running",
                                stage="downloading_preprocessor",
                                message=f"Downloading DWPose/OpenPose preprocessors: {pct}%",
                                percent=pct,
                            )
                _update_openpose_progress(
                    job_id,
                    status="running",
                    stage="extracting_preprocessor",
                    message="Extracting DWPose/OpenPose preprocessors",
                )
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(tmp)
                extracted = os.path.join(tmp, "comfyui_controlnet_aux-main")
                if not os.path.isdir(extracted):
                    raise RuntimeError("Downloaded comfyui_controlnet_aux archive did not contain the expected folder.")
                shutil.move(extracted, repo_path)

    requirements = os.path.join(repo_path, "requirements.txt")
    if os.path.isfile(requirements) and _controlnet_aux_requirements_missing():
        _update_openpose_progress(
            job_id,
            status="running",
            stage="installing_requirements",
            message="Installing DWPose/OpenPose Python requirements",
        )
        subprocess.run(
            [sys.executable, "-s", "-m", "pip", "install", "-r", requirements],
            check=True,
        )


def _load_controlnet_aux_mappings(repo_path, comfy_nodes, job_id=None):
    import importlib.util
    import sys

    init_path = os.path.join(repo_path, "__init__.py")
    if not os.path.isfile(init_path):
        return False

    parent = os.path.dirname(repo_path)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    src_path = os.path.join(repo_path, "src")
    if os.path.isdir(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)

    package_name = _ADVANCED_POSE_CONTROLNET_AUX_DIR
    module = sys.modules.get(package_name)
    if module is None:
        _update_openpose_progress(
            job_id,
            status="running",
            stage="loading_preprocessor",
            message="Loading DWPose/OpenPose preprocessors",
        )
        spec = importlib.util.spec_from_file_location(
            package_name,
            init_path,
            submodule_search_locations=[repo_path],
        )
        if spec is None or spec.loader is None:
            return False
        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module
        spec.loader.exec_module(module)

    node_mappings = getattr(module, "NODE_CLASS_MAPPINGS", {}) or {}
    display_mappings = getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {}) or {}
    if not _has_pose_preprocessor_mapping(node_mappings):
        node_mappings = {}
        display_mappings = {}
        for wrapper_name in ["dwpose", "openpose"]:
            wrapper_module_name = f"{package_name}.node_wrappers.{wrapper_name}"
            wrapper = sys.modules.get(wrapper_module_name)
            if wrapper is None:
                wrapper_path = os.path.join(repo_path, "node_wrappers", f"{wrapper_name}.py")
                if not os.path.isfile(wrapper_path):
                    continue
                spec = importlib.util.spec_from_file_location(wrapper_module_name, wrapper_path)
                if spec is None or spec.loader is None:
                    continue
                wrapper = importlib.util.module_from_spec(spec)
                sys.modules[wrapper_module_name] = wrapper
                spec.loader.exec_module(wrapper)
            node_mappings.update(getattr(wrapper, "NODE_CLASS_MAPPINGS", {}) or {})
            display_mappings.update(getattr(wrapper, "NODE_DISPLAY_NAME_MAPPINGS", {}) or {})

    getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}).update(node_mappings)
    if hasattr(comfy_nodes, "NODE_DISPLAY_NAME_MAPPINGS"):
        comfy_nodes.NODE_DISPLAY_NAME_MAPPINGS.update(display_mappings)
    return _has_pose_preprocessor_mapping(getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}) or {})


def _ensure_pose_preprocessors_available(comfy_nodes, job_id=None):
    global _ADVANCED_POSE_PREPROCESSOR_INSTALL_ATTEMPTED

    _update_openpose_progress(
        job_id,
        status="running",
        stage="checking_preprocessors",
        message="Checking DWPose/OpenPose preprocessors",
    )
    mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}) or {}
    if _has_pose_preprocessor_mapping(mappings):
        return

    with _ADVANCED_POSE_PREPROCESSOR_INSTALL_LOCK:
        mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}) or {}
        if _has_pose_preprocessor_mapping(mappings):
            return

        repo_path = None
        for candidate in _controlnet_aux_candidate_paths():
            if os.path.isdir(candidate):
                repo_path = candidate
                break
        if repo_path is None:
            repo_path = os.path.join(_custom_nodes_root(), _ADVANCED_POSE_CONTROLNET_AUX_DIR)

        if not os.path.isdir(repo_path) or not _ADVANCED_POSE_PREPROCESSOR_INSTALL_ATTEMPTED:
            _ADVANCED_POSE_PREPROCESSOR_INSTALL_ATTEMPTED = True
            _install_controlnet_aux_custom_node(repo_path, job_id=job_id)

        if not _load_controlnet_aux_mappings(repo_path, comfy_nodes, job_id=job_id):
            raise RuntimeError(
                "Installed comfyui_controlnet_aux, but ComfyUI did not register DWPose/OpenPose nodes. "
                "Restart ComfyUI once so the new custom node can finish loading."
            )


def _run_comfy_openpose_detector(image_tensor, resolution=512, job_id=None):
    try:
        import nodes as comfy_nodes
    except Exception as e:
        raise RuntimeError(f"ComfyUI node registry unavailable: {e}") from e

    _ensure_pose_preprocessors_available(comfy_nodes, job_id=job_id)
    mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}) or {}
    attempts = []

    def _run():
        progress_callback = _install_openpose_progress_callback(job_id)
        try:
            detector_specs = [
                ("DWPreprocessor", {
                    "detect_hand": "enable",
                    "detect_body": "enable",
                    "detect_face": "enable",
                    "resolution": resolution,
                    "bbox_detector": "yolox_l.onnx",
                    "pose_estimator": "dw-ll_ucoco_384.onnx",
                }),
                ("AIO_Preprocessor", {
                    "preprocessor": "dw_openpose_full",
                    "resolution": resolution,
                }),
                ("OpenposePreprocessor", {
                    "detect_hand": "enable",
                    "detect_body": "enable",
                    "detect_face": "enable",
                    "resolution": resolution,
                }),
                ("AIO_Preprocessor", {
                    "preprocessor": "openpose_full",
                    "resolution": resolution,
                }),
            ]

            for node_name, kwargs in detector_specs:
                cls = mappings.get(node_name)
                if cls is None:
                    attempts.append(f"{node_name}: not installed")
                    continue

                try:
                    _update_openpose_progress(
                        job_id,
                        status="running",
                        stage="detecting_pose",
                        message=f"Detecting skeleton with {node_name}",
                    )
                    node = cls()
                    fn = getattr(node, getattr(cls, "FUNCTION", "estimate_pose"))
                    result = fn(image=image_tensor, **kwargs)
                    payload = _extract_openpose_payload(result)
                    if payload:
                        return payload, node_name
                    attempts.append(f"{node_name}: no keypoints returned")
                except TypeError:
                    try:
                        _update_openpose_progress(
                            job_id,
                            status="running",
                            stage="detecting_pose",
                            message=f"Detecting skeleton with {node_name}",
                        )
                        minimal = {k: v for k, v in kwargs.items() if k in {"detect_hand", "detect_body", "detect_face", "resolution"}}
                        node = cls()
                        fn = getattr(node, getattr(cls, "FUNCTION", "estimate_pose"))
                        result = fn(image=image_tensor, **minimal)
                        payload = _extract_openpose_payload(result)
                        if payload:
                            return payload, node_name
                        attempts.append(f"{node_name}: no keypoints returned")
                    except Exception as e:
                        attempts.append(f"{node_name}: {e}")
                except Exception as e:
                    attempts.append(f"{node_name}: {e}")

            raise RuntimeError("; ".join(attempts) or "no OpenPose detector available")
        finally:
            _restore_openpose_progress_callback(progress_callback)

    return _run_node_with_prompt_context(_run)


def _run_comfy_depth_detector(image_tensor, resolution=512):
    try:
        import nodes as comfy_nodes
    except Exception as e:
        raise RuntimeError(f"ComfyUI node registry unavailable: {e}") from e

    mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}) or {}
    attempts = []

    def _run():
        detector_specs = [
            ("AIO_Preprocessor", {
                "preprocessor": "DepthAnythingV2Preprocessor",
                "resolution": resolution,
            }),
            ("DepthAnythingV2Preprocessor", {
                "resolution": resolution,
            }),
            ("Zoe_DepthMapPreprocessor", {
                "resolution": resolution,
            }),
            ("MiDaS_DepthMapPreprocessor", {
                "a": 6.283185307179586,
                "bg_threshold": 0.1,
                "resolution": resolution,
            }),
        ]

        for node_name, kwargs in detector_specs:
            cls = mappings.get(node_name)
            if cls is None:
                attempts.append(f"{node_name}: not installed")
                continue

            try:
                node = cls()
                fn = getattr(node, getattr(cls, "FUNCTION", "execute"))
                result = fn(image=image_tensor, **kwargs)
                payload = _extract_image_tensor_payload(result)
                if payload is not None:
                    return payload, node_name
                attempts.append(f"{node_name}: no depth image returned")
            except TypeError:
                try:
                    minimal = {k: v for k, v in kwargs.items() if k == "resolution"}
                    node = cls()
                    fn = getattr(node, getattr(cls, "FUNCTION", "execute"))
                    result = fn(image=image_tensor, **minimal)
                    payload = _extract_image_tensor_payload(result)
                    if payload is not None:
                        return payload, node_name
                    attempts.append(f"{node_name}: no depth image returned")
                except Exception as e:
                    attempts.append(f"{node_name}: {e}")
            except Exception as e:
                attempts.append(f"{node_name}: {e}")

        raise RuntimeError("; ".join(attempts) or "no depth detector available")

    return _run_node_with_prompt_context(_run)


def _first_openpose_person(openpose_payload):
    if isinstance(openpose_payload, list):
        if not openpose_payload:
            return None
        return _first_openpose_person(openpose_payload[0])
    if not isinstance(openpose_payload, dict):
        return None
    people = openpose_payload.get("people")
    if isinstance(people, list) and people:
        return people[0]
    return None


def _openpose_joint_names(count):
    coco18 = [
        "nose", "neck", "r_shoulder", "r_elbow", "r_wrist", "l_shoulder",
        "l_elbow", "l_wrist", "r_hip", "r_knee", "r_ankle", "l_hip",
        "l_knee", "l_ankle", "r_eye", "l_eye", "r_ear", "l_ear"
    ]
    body25 = [
        "nose", "neck", "r_shoulder", "r_elbow", "r_wrist", "l_shoulder",
        "l_elbow", "l_wrist", "mid_hip", "r_hip", "r_knee", "r_ankle",
        "l_hip", "l_knee", "l_ankle", "r_eye", "l_eye", "r_ear", "l_ear"
    ]
    return body25 if count >= 25 else coco18


def _sample_openpose_joint_depths(openpose_payload, depth_tensor):
    import numpy as np

    person = _first_openpose_person(openpose_payload)
    if not person:
        return {}
    keypoints = person.get("pose_keypoints_2d") or []
    if len(keypoints) < 3:
        return {}

    arr = depth_tensor
    try:
        if hasattr(arr, "detach"):
            arr = arr.detach().cpu().numpy()
        arr = np.asarray(arr)
    except Exception:
        return {}

    if arr.ndim == 4:
        arr = arr[0]
    if arr.ndim == 3:
        arr = arr.mean(axis=2)
    if arr.ndim != 2:
        return {}

    h, w = arr.shape
    num = len(keypoints) // 3
    names = _openpose_joint_names(num)
    canvas_w = float(openpose_payload[0].get("canvas_width") if isinstance(openpose_payload, list) and openpose_payload else openpose_payload.get("canvas_width", w))
    canvas_h = float(openpose_payload[0].get("canvas_height") if isinstance(openpose_payload, list) and openpose_payload else openpose_payload.get("canvas_height", h))
    if canvas_w <= 0: canvas_w = w
    if canvas_h <= 0: canvas_h = h

    samples = {}
    valid_values = []
    for idx, name in enumerate(names[:num]):
        x = float(keypoints[idx * 3] or 0)
        y = float(keypoints[idx * 3 + 1] or 0)
        c = float(keypoints[idx * 3 + 2] or 0)
        if c <= 0.05 or x <= 0 or y <= 0:
            continue
        px = int(max(0, min(w - 1, round((x / canvas_w) * (w - 1)))))
        py = int(max(0, min(h - 1, round((y / canvas_h) * (h - 1)))))
        value = float(arr[py, px])
        samples[name] = value
        valid_values.append(value)

    if not valid_values:
        return {}

    lo = min(valid_values)
    hi = max(valid_values)
    span = hi - lo
    if span < 1e-6:
        return {name: 0.0 for name in samples}

    return {name: ((value - lo) / span) * 2.0 - 1.0 for name, value in samples.items()}


def _advanced_pose_register_pose_studio_openpose():
    try:
        from server import PromptServer
        from aiohttp import web
    except Exception:
        return

    @PromptServer.instance.routes.get("/advanced_pose_studio/openpose_progress/{job_id}")
    async def advanced_pose_studio_openpose_progress(request):
        job_id = request.match_info["job_id"]
        state = _ADVANCED_POSE_OPENPOSE_PROGRESS.get(job_id)
        if not state:
            return web.json_response({"status": "idle", "message": ""})
        return web.json_response(state)

    @PromptServer.instance.routes.post("/advanced_pose_studio/openpose_from_image")
    async def advanced_pose_studio_openpose_from_image(request):
        try:
            import asyncio

            data = await request.json()
            job_id = data.get("job_id")
            resolution = int(data.get("resolution", 512))
            resolution = max(64, min(2048, resolution))

            def _detect():
                _update_openpose_progress(
                    job_id,
                    status="running",
                    stage="preparing",
                    message="Preparing image for skeleton detection",
                )
                image = _decode_data_url_image(data.get("image"))
                tensor = _pil_to_comfy_image_tensor(image)
                openpose_payload, detector = _run_comfy_openpose_detector(tensor, resolution=resolution, job_id=job_id)
                depth_samples = {}
                depth_detector = None
                depth_error = None
                try:
                    _update_openpose_progress(
                        job_id,
                        status="running",
                        stage="detecting_depth",
                        message="Sampling depth for detected skeleton",
                    )
                    depth_tensor, depth_detector = _run_comfy_depth_detector(tensor, resolution=resolution)
                    depth_samples = _sample_openpose_joint_depths(openpose_payload, depth_tensor)
                except Exception as depth_exc:
                    depth_error = str(depth_exc)

                _update_openpose_progress(
                    job_id,
                    status="complete",
                    stage="complete",
                    message="Skeleton detection complete",
                    percent=100,
                )
                return openpose_payload, detector, depth_detector, depth_samples, depth_error

            openpose_payload, detector, depth_detector, depth_samples, depth_error = await asyncio.to_thread(_detect)
            return web.json_response({
                "status": "ok",
                "detector": detector,
                "openpose": openpose_payload,
                "depth_detector": depth_detector,
                "depth_samples": depth_samples,
                "depth_error": depth_error,
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            _update_openpose_progress(
                data.get("job_id") if "data" in locals() else None,
                status="error",
                stage="error",
                message=str(e),
            )
            return web.json_response({"error": str(e)}, status=500)


_advanced_pose_register_pose_studio_openpose()


_ADVANCED_POSE_QWEN_MULTI_ANGLE_CACHE = {}
_ADVANCED_POSE_QWEN_MULTI_ANGLE_PROGRESS = {}
_ADVANCED_POSE_QWEN_MULTI_ANGLE_STEPS = 4
_ADVANCED_POSE_QWEN_MULTI_ANGLE_MODEL_MANIFEST = {
    "clip": {
        "model_type": "text_encoders",
        "preferred": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "aliases": ["qwen_2.5_vl_7b_fp8_scaled.safetensors"],
        "url": "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
    },
    "vae": {
        "model_type": "vae",
        "preferred": "qwen_image_vae.safetensors",
        "aliases": ["qwen_image_vae.safetensors"],
        "url": "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors",
    },
    "unet": {
        "model_type": "diffusion_models",
        "preferred": "Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors",
        "aliases": [
            "Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors",
            "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        ],
        "url": "https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors",
    },
    "lightning_lora": {
        "model_type": "loras",
        "preferred": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        "aliases": ["Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"],
        "url": "https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
    },
    "angle_lora": {
        "model_type": "loras",
        "preferred": "qwen-image-edit-2511-multiple-angles-lora.safetensors",
        "aliases": ["qwen-image-edit-2511-multiple-angles-lora.safetensors"],
        "url": "https://huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA/resolve/main/qwen-image-edit-2511-multiple-angles-lora.safetensors",
    },
}


def _node_output_first(value):
    if hasattr(value, "result"):
        result = value.result
        if isinstance(result, (list, tuple)):
            return result[0]
        return result
    if isinstance(value, (list, tuple)):
        return value[0]
    return value


def _node_output_tuple(value):
    if hasattr(value, "result"):
        result = value.result
        if isinstance(result, (list, tuple)):
            return tuple(result)
        return (result,)
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _pil_to_resized_comfy_tensor(image, width=1024, height=1024):
    import numpy as np
    import torch
    from PIL import Image

    img = image.convert("RGB")
    img.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(img, ((width - img.width) // 2, (height - img.height) // 2))
    arr = np.asarray(canvas).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None,]


def _comfy_tensor_to_data_url(tensor):
    import base64
    import io
    import numpy as np
    from PIL import Image

    if hasattr(tensor, "detach"):
        tensor = tensor.detach().cpu().numpy()
    arr = np.asarray(tensor)
    if arr.ndim == 4:
        arr = arr[0]
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    image = Image.fromarray(arr[:, :, :3], "RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"


def _get_comfy_node_class(name):
    import nodes as comfy_nodes

    cls = (getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}) or {}).get(name)
    if cls is not None:
        return cls
    if name == "TextEncodeQwenImageEditPlus":
        from comfy_extras.nodes_qwen import TextEncodeQwenImageEditPlus
        return TextEncodeQwenImageEditPlus
    if name == "ReferenceLatent":
        from comfy_extras.nodes_edit_model import ReferenceLatent
        return ReferenceLatent
    if name == "ModelSamplingAuraFlow":
        from comfy_extras.nodes_model_advanced import ModelSamplingAuraFlow
        return ModelSamplingAuraFlow
    if name == "CFGNorm":
        from comfy_extras.nodes_cfg import CFGNorm
        return CFGNorm
    raise RuntimeError(f"Comfy node class not found: {name}")


def _filename_in_comfy_list(model_type, aliases):
    import folder_paths

    wanted = set(aliases or [])
    try:
        for name in folder_paths.get_filename_list(model_type):
            normalized = name.replace("\\", "/")
            if name in wanted or any(normalized.endswith("/" + alias) for alias in wanted):
                return name
    except Exception:
        pass
    return None


def _download_model_to_comfy_folder(model_type, filename, url, job_id=None, label=None):
    import os
    import urllib.request
    import folder_paths

    folders = folder_paths.get_folder_paths(model_type)
    if not folders:
        raise RuntimeError(f"ComfyUI has no registered model folder for '{model_type}'")

    target = os.path.join(folders[0], filename)
    part = target + ".part"
    os.makedirs(os.path.dirname(target), exist_ok=True)

    _update_qwen_multi_angle_progress(
        job_id,
        status="running",
        stage="downloading_model",
        message=f"Downloading {label or filename}",
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Advanced-Pose-Studio"})
    with urllib.request.urlopen(req, timeout=120) as response, open(part, "wb") as f:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                pct = round((done / total) * 100, 1)
                _update_qwen_multi_angle_progress(
                    job_id,
                    status="running",
                    stage="downloading_model",
                    message=f"Downloading {label or filename}: {pct}%",
                )
    os.replace(part, target)
    return filename


def _ensure_qwen_multi_angle_model(key, job_id=None):
    spec = _ADVANCED_POSE_QWEN_MULTI_ANGLE_MODEL_MANIFEST[key]
    found = _filename_in_comfy_list(spec["model_type"], spec["aliases"])
    if found:
        return found

    return _download_model_to_comfy_folder(
        spec["model_type"],
        spec["preferred"],
        spec["url"],
        job_id=job_id,
        label=spec["preferred"],
    )


def _ensure_qwen_multi_angle_models(job_id=None):
    resolved = {}
    for key in ["vae", "clip", "unet", "lightning_lora", "angle_lora"]:
        _update_qwen_multi_angle_progress(
            job_id,
            status="running",
            stage="checking_models",
            message=f"Checking {key.replace('_', ' ')}",
        )
        resolved[key] = _ensure_qwen_multi_angle_model(key, job_id=job_id)
    return resolved


def _qwen_multi_angle_models(job_id=None):
    import torch

    if _ADVANCED_POSE_QWEN_MULTI_ANGLE_CACHE.get("models"):
        return _ADVANCED_POSE_QWEN_MULTI_ANGLE_CACHE["models"]

    resolved = _ensure_qwen_multi_angle_models(job_id=job_id)

    VAELoader = _get_comfy_node_class("VAELoader")
    CLIPLoader = _get_comfy_node_class("CLIPLoader")
    UNETLoader = _get_comfy_node_class("UNETLoader")
    LoraLoader = _get_comfy_node_class("LoraLoader")

    with torch.inference_mode():
        vae = VAELoader().load_vae(resolved["vae"])[0]
        clip = CLIPLoader().load_clip(resolved["clip"], "qwen_image", "default")[0]
        model = UNETLoader().load_unet(resolved["unet"], "default")[0]

        lora = LoraLoader()
        model = lora.load_lora(model, clip, resolved["lightning_lora"], 1, 1)[0]
        model = lora.load_lora(model, clip, resolved["angle_lora"], 1, 1)[0]

        model = _node_output_first(_get_comfy_node_class("ModelSamplingAuraFlow")().patch_aura(model, 3))
        model = _node_output_first(_get_comfy_node_class("CFGNorm").execute(model, 1))

    _ADVANCED_POSE_QWEN_MULTI_ANGLE_CACHE["models"] = {
        "vae": vae,
        "clip": clip,
        "model": model,
    }
    return _ADVANCED_POSE_QWEN_MULTI_ANGLE_CACHE["models"]


def _update_qwen_multi_angle_progress(job_id, **kwargs):
    if not job_id:
        return
    import time

    state = _ADVANCED_POSE_QWEN_MULTI_ANGLE_PROGRESS.get(job_id, {})
    state.update(kwargs)
    state["updated_at"] = time.time()
    _ADVANCED_POSE_QWEN_MULTI_ANGLE_PROGRESS[job_id] = state

    now = time.time()
    for key, value in list(_ADVANCED_POSE_QWEN_MULTI_ANGLE_PROGRESS.items()):
        if now - value.get("updated_at", now) > 600:
            _ADVANCED_POSE_QWEN_MULTI_ANGLE_PROGRESS.pop(key, None)


def _qwen_direct_sample(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent, denoise, progress_cb=None):
    import torch
    import comfy.sample

    latent_image = latent["samples"]
    latent_image = comfy.sample.fix_empty_latent_channels(model, latent_image, latent.get("downscale_ratio_spacial", None))
    batch_inds = latent["batch_index"] if "batch_index" in latent else None
    noise = comfy.sample.prepare_noise(latent_image, seed, batch_inds)
    noise_mask = latent.get("noise_mask")

    def callback(step, _x0, _x, total_steps):
        if progress_cb:
            progress_cb(step + 1, total_steps)

    samples = comfy.sample.sample(
        model,
        noise,
        steps,
        cfg,
        sampler_name,
        scheduler,
        positive,
        negative,
        latent_image,
        denoise=denoise,
        noise_mask=noise_mask,
        callback=callback,
        disable_pbar=True,
        seed=seed,
    )
    out = latent.copy()
    out.pop("downscale_ratio_spacial", None)
    out["samples"] = samples
    return out


def _run_qwen_multi_angle_direct(image, prompt, seed=None, job_id=None, angle_index=0, angle_total=1, angle_label=None):
    import random
    import torch

    def _run():
        VAEEncode = _get_comfy_node_class("VAEEncode")
        VAEDecode = _get_comfy_node_class("VAEDecode")
        TextEncodeQwenImageEditPlus = _get_comfy_node_class("TextEncodeQwenImageEditPlus")
        ReferenceLatent = _get_comfy_node_class("ReferenceLatent")

        models = _qwen_multi_angle_models(job_id=job_id)
        vae = models["vae"]
        clip = models["clip"]
        model = models["model"]
        local_seed = int(seed if seed is not None else random.randint(1, 2**63 - 1))
        label = angle_label or f"Angle {angle_index + 1}"

        with torch.inference_mode():
            _update_qwen_multi_angle_progress(
                job_id,
                status="running",
                stage="preparing",
                message=f"{label}: preparing image",
                angle_index=angle_index,
                angle_total=angle_total,
                angle_label=label,
                sampler_step=0,
                sampler_steps=_ADVANCED_POSE_QWEN_MULTI_ANGLE_STEPS,
                percent=0,
            )
            pixels = _pil_to_resized_comfy_tensor(image, 1024, 1024)
            latent = VAEEncode().encode(vae, pixels)[0]

            _update_qwen_multi_angle_progress(job_id, stage="conditioning", message=f"{label}: encoding prompt")
            negative = _node_output_first(TextEncodeQwenImageEditPlus.execute(clip, "", vae=vae))
            negative = _node_output_first(ReferenceLatent.execute(negative, latent))

            positive = _node_output_first(TextEncodeQwenImageEditPlus.execute(clip, prompt, vae=vae))
            positive = _node_output_first(ReferenceLatent.execute(positive, latent))

            _update_qwen_multi_angle_progress(job_id, stage="sampling", message=f"{label}: sampling 0/{_ADVANCED_POSE_QWEN_MULTI_ANGLE_STEPS}")

            def on_sample_step(step, total_steps):
                angle_fraction = angle_index / max(1, angle_total)
                step_fraction = (step / max(1, total_steps)) / max(1, angle_total)
                _update_qwen_multi_angle_progress(
                    job_id,
                    status="running",
                    stage="sampling",
                    message=f"{label}: sampling {step}/{total_steps}",
                    sampler_step=step,
                    sampler_steps=total_steps,
                    percent=round((angle_fraction + step_fraction) * 100, 1),
                )

            samples = _qwen_direct_sample(
                model=model,
                seed=local_seed,
                steps=_ADVANCED_POSE_QWEN_MULTI_ANGLE_STEPS,
                cfg=1,
                sampler_name="euler",
                scheduler="simple",
                positive=positive,
                negative=negative,
                latent=latent,
                denoise=1,
                progress_cb=on_sample_step,
            )
            _update_qwen_multi_angle_progress(job_id, stage="decoding", message=f"{label}: decoding")
            decoded = VAEDecode().decode(vae, samples)[0]

        return _comfy_tensor_to_data_url(decoded)

    return _run_node_with_prompt_context(_run)


def _advanced_pose_register_pose_studio_multi_angle():
    try:
        from server import PromptServer
        from aiohttp import web
    except Exception:
        return

    @PromptServer.instance.routes.get("/advanced_pose_studio/qwen_multi_angle_progress/{job_id}")
    async def advanced_pose_studio_qwen_multi_angle_progress(request):
        job_id = request.match_info["job_id"]
        state = _ADVANCED_POSE_QWEN_MULTI_ANGLE_PROGRESS.get(job_id)
        if not state:
            return web.json_response({"status": "idle", "message": ""})
        return web.json_response(state)

    @PromptServer.instance.routes.post("/advanced_pose_studio/qwen_multi_angle")
    async def advanced_pose_studio_qwen_multi_angle(request):
        try:
            import asyncio
            import time

            data = await request.json()
            source = _decode_data_url_image(data.get("image"))
            job_id = data.get("job_id")

            prompts = data.get("prompts") or [
                "Rotate camera 45 degrees left. Preserve the exact person, clothing, body pose, limb positions, proportions, and background as much as possible.",
                "Rotate camera 45 degrees right. Preserve the exact person, clothing, body pose, limb positions, proportions, and background as much as possible.",
                "Rotate camera 90 degrees left side view. Preserve the exact person, clothing, body pose, limb positions, proportions, and background as much as possible.",
            ]
            prompts = [str(p) for p in prompts[:4]]

            generated = []
            total = len(prompts)
            _update_qwen_multi_angle_progress(
                job_id,
                status="running",
                stage="starting",
                message=f"Starting multi-angle generation: {total} angles",
                angle_index=0,
                angle_total=total,
                sampler_step=0,
                sampler_steps=_ADVANCED_POSE_QWEN_MULTI_ANGLE_STEPS,
                percent=0,
            )
            for idx, prompt_text in enumerate(prompts):
                seed = int(time.time() * 1000) + idx
                label = f"Angle {idx + 1}/{total}"
                image_data_url = await asyncio.to_thread(
                    _run_qwen_multi_angle_direct,
                    source,
                    prompt_text,
                    seed,
                    job_id,
                    idx,
                    total,
                    label,
                )
                generated.append({
                    "label": f"Angle {idx + 1}",
                    "prompt": prompt_text,
                    "image": image_data_url,
                })
                _update_qwen_multi_angle_progress(
                    job_id,
                    status="running",
                    stage="angle_done",
                    message=f"{label}: complete",
                    angle_index=idx,
                    angle_total=total,
                    percent=round(((idx + 1) / max(1, total)) * 100, 1),
                )

            _update_qwen_multi_angle_progress(
                job_id,
                status="complete",
                stage="complete",
                message="Multi-angle generation complete",
                percent=100,
            )
            return web.json_response({"status": "ok", "images": generated})
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                _update_qwen_multi_angle_progress(data.get("job_id") if "data" in locals() else None, status="error", stage="error", message=str(e))
            except Exception:
                pass
            return web.json_response({"error": str(e)}, status=500)


_advanced_pose_register_pose_studio_multi_angle()


def _advanced_pose_register_pose_studio_roster_cache():
    try:
        from server import PromptServer
        from aiohttp import web
        from .nodes.pose_studio import POSE_STUDIO_CHARACTER_ROSTER_CACHE
    except Exception:
        return

    @PromptServer.instance.routes.get("/advanced_pose_studio/character_roster/{node_id}")
    async def advanced_pose_studio_character_roster_get(request):
        node_id = request.match_info["node_id"]
        entry = POSE_STUDIO_CHARACTER_ROSTER_CACHE.get(str(node_id))
        if not entry:
            return web.json_response({"characters": []})
        return web.json_response(entry)


_advanced_pose_register_pose_studio_roster_cache()
