# Advanced Pose Studio

Advanced Pose Studio is a standalone ComfyUI custom node for staging MakeHuman-based character meshes, editing poses, and exporting viewport-aligned pose renders.

## Node

- Node id: `Advanced_Pose_Studio`
- Display name: `Advanced Pose Studio`
- Category: `Advanced Pose Studio`

## Inputs

- `pose_data`: internal serialized scene state managed by the node UI.
- `characters_json` optional input: creates up to four scene characters from a character roster JSON.

## Outputs

- `images`: rendered viewport image list.
- `lighting_prompt`: prompt text generated from the scene lighting/context state.
- `background_only`: the current viewport background as an image.
- `character_1` to `character_4`: individual character renders on white backgrounds for downstream image editing tools.

## Main Features

- Interactive Three.js viewport embedded inside the ComfyUI node.
- Up to four character meshes in one scene.
- Add, delete, select, move, and rotate characters.
- Character list stays synchronized with viewport selection.
- Color-coded character slots: blue, yellow, red, green.
- Per-character mesh controls for age, sex, weight, muscle, height, and body proportions.
- Full-viewport background image support.
- Pose and Move modes with separate point and character gizmo behavior.
- Move Points mode for IK-supported joints without falling back to an accidental rotation gizmo.
- Pose library save/load support with previews.
- Import/export support for pose data.
- Client-side viewport capture so output matches what is visible in the node.

## Pose Initializer

The Pose Initializer can load a source image and convert it to an editable OpenPose skeleton preview before applying it to the selected character.

Before loading an image, the UI asks for one of two modes:

- Single Angle: runs OpenPose/DWPose on the uploaded image only. This is faster and works best when the body is visible and clear.
- Multi Angle: generates additional camera angles using Qwen Image Edit, detects skeletons on each generated view, and combines the views to improve the 3D pose. This takes longer and may download required Qwen models if they are missing.

The preview supports editable body, hand, and face keypoints when the installed preprocessor returns them. Missing limbs can be manually added or corrected before applying the pose.

## Optional Character JSON

When connected, `characters_json` can create characters from a roster structure containing:

- `selected_count`
- `characters_dir`
- `characters`

Each character entry can include fields such as `NAME`, `VISUAL`, `ATTIRE`, `PERSONALITY`, and `BACKSTORY`. The node uses these fields to infer a basic mesh profile and name the character. If a matching image exists in `characters_dir`, it appears in the character list.

## Model Requirements

Core mesh posing uses the included MakeHuman data in `CharacterData/`.

OpenPose initialization uses installed ComfyUI preprocessors when available:

- DWPose is preferred when installed.
- OpenPose is used as fallback when available.
- Depth preprocessors are sampled when available to improve pose transfer.

Multi-angle mode uses native ComfyUI nodes directly and checks/downloads the required Qwen Image Edit model, VAE, text encoder, Lightning LoRA, and multi-angle LoRA when missing.

## Runtime Files

The isolated package keeps only the Pose Studio runtime:

- `nodes/pose_studio.py`
- `api/pose_library.py`
- `CharacterData/`
- `PoseLibrary/`
- `web/advanced_pose_studio.js`
- `web/advanced_pose_studio_core.js`
- `web/advanced_openpose_import.js`
- `web/three.module.js`
- `web/OrbitControls.js`
- `web/TransformControls.js`
- `web/textures/`

## Installation

Place this folder in `ComfyUI/custom_nodes`, install the listed Python requirements if needed, and restart ComfyUI.
