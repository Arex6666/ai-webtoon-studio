# AI Webtoon Studio - Chapter Bundle Specification v1

**Version**: 1.0
**Status**: Implemented

This document defines the structure and schema for the "Chapter Bundle" export artifact. This bundle is the standardized delivery package for downstream consumption (publishing, archiving, post-production).

## 1. Directory Structure

The bundle is a ZIP archive with the following structure:

```text
chapter_bundle.zip
├── manifest.json                 # [Required] Root manifest
├── chapter.json                  # [Required] Chapter metadata snapshot
├── assets.json                   # [Required] Asset version locking (models, LORAs)
├── provenance/
│   └── jobs.json                 # [Required] Job execution history
├── panels/
│   ├── 0001/                     # Panel index (4 digits)
│   │   ├── panel.json            # [Required] Panel metadata snapshot
│   │   ├── qa.json               # [Optional] Quality assurance results
│   │   ├── layerpack/            # LayerPack artifacts
│   │   │   ├── manifest.json     # [Required] LayerPack manifest
│   │   │   ├── full.png          # [Required] Final composite image
│   │   │   ├── character.png     # [Optional] Character layer
│   │   │   ├── background.png    # [Optional] Background layer
│   │   │   └── ...
│   │   └── typeset/              # Typesetting artifacts
│   │       ├── bubbles.json      # [Optional] Bubble data
│   │       └── typeset.png       # [Optional] Image with text
│   └── ...
└── README.txt                    # [Optional] Instructions
```

## 2. Manifest Schemas

### 2.1 Bundle Manifest (`manifest.json`)
The root entry point for the bundle.

```json
{
  "spec_version": "1.0",
  "bundle_id": "uuid-string",
  "created_at": "ISO-8601 timestamp",
  "chapter": {
    "id": "uuid",
    "title": "Chapter 1",
    "version": 1
  },
  "panels": [
    {
      "panel_id": "uuid",
      "panel_index": 1,
      "dir_name": "0001"
    },
    ...
  ],
  "stats": {
    "total_panels": 20,
    "total_size_bytes": 104857600
  },
  "qa_summary": {
    "passed": true,
    "avg_score": 0.95
  }
}
```

### 2.2 LayerPack Manifest (`layerpack/manifest.json`)
The authoritative source for panel assets and reproducibility.

```json
{
  "spec_version": "1.0",
  "layerpack_id": "uuid",
  "panel_id": "uuid",
  "provenance": {
    "model_urn": "urn:model:sdxl:v1.0",
    "workflow_id": "comfy-workflow-hash",
    "params": {
      "seed": 123456,
      "steps": 30,
      "cfg": 7.0
    }
  },
  "files": {
    "full": "full.png",
    "character": "character.png",
    "background": "background.png"
  },
  "geometry": {
    "width": 1024,
    "height": 1024
  }
}
```

### 2.3 Assets Lock (`assets.json`)
Records exact versions of all models used.

```json
{
  "models": [
    {
      "name": "SDXL Base",
      "hash": "sha256:...",
      "source": "https://huggingface.co/..."
    }
  ],
  "loras": [...]
}
```

## 3. Implementation Mappings

- **Backend Schemas**: `apps/api/app/schemas/bundle_manifest.py` & `layerpack_manifest.py` (Pydantic)
- **Frontend Schemas**: `apps/web/src/lib/schema/job.ts` (Zod validation for export jobs)
- **Builder Service**: `apps/api/app/services/export/bundle_builder.py`

## 4. Verification

Use the `manifest.json` to validate the integrity of the bundle. All paths in manifests are relative to their directory.
