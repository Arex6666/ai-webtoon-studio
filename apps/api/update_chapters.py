import re

filepath = r'd:\ai-webtoon-studio\apps\api\app\api\routes\chapters.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the summary dict closing
old_pattern = '"scene_id": scene_id\n        }'
new_content = '''"scene_id": scene_id,
            # 结构化字段 (从 spec_json 提取)
            "shot_type": spec.get("shot", {}).get("shotType") or spec.get("shot_type"),
            "camera_move": spec.get("shot", {}).get("cameraMove") or spec.get("camera", {}).get("move"),
            "camera_angle": spec.get("camera", {}).get("angle") or spec.get("camera_angle"),
            "duration_sec": spec.get("shot", {}).get("durationSec") or spec.get("suggested_duration"),
            "location": spec.get("scene", {}).get("location") or spec.get("scene_description"),
            "time_of_day": spec.get("scene", {}).get("timeOfDay") or spec.get("time_of_day"),
            "mood": spec.get("scene", {}).get("mood"),
            "emotion": spec.get("emotion"),
            "action_description": spec.get("action_description") or spec.get("description", "")
        }'''

if old_pattern in content:
    content = content.replace(old_pattern, new_content, 1)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Successfully updated chapters.py')
else:
    print('Pattern not found')
    # Debug: show surrounding content
    idx = content.find('"scene_id": scene_id')
    if idx >= 0:
        print(f'Found at {idx}: {repr(content[idx:idx+50])}')
