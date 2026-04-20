import re

complex_files = [
    'bundle_manifest.py', 
    'layerpack_manifest.py', 
    'chapter_layout.py', 
    'panel_spec.py', 
    'assets_lock.py', 
    'layer_pack_meta.py'
]

for cf in complex_files:
    path = f'apps/api/app/schemas/{cf}'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    orig = content
    
    if 'class Config:' in content:
        if 'from pydantic import ' in content and 'ConfigDict' not in content:
            content = content.replace('from pydantic import ', 'from pydantic import ConfigDict, ', 1)
        elif 'from pydantic import' not in content and 'import pydantic' not in content:
            content = 'from pydantic import ConfigDict\n' + content
    
        def repl(m):
            indent = m.group(1)
            body = m.group(2)
            body = body.rstrip()
            return f'{indent}model_config = ConfigDict(\n{body}\n{indent})'
            
        pattern = r'([ \t]*)class Config:\n((?:(?:\1[ \t]+[^\n]*\n)|(?:[ \t]*\n))+)'
        content = re.sub(pattern, repl, content)
        
        content = re.sub(r'json_schema_extra\s*=\s*\{', 'json_schema_extra={', content)
        content = re.sub(r'json_encoders\s*=\s*\{', 'json_encoders={', content)
        content = content.replace('use_enum_values = True', 'use_enum_values=True,')
        content = content.replace('populate_by_name = True', 'populate_by_name=True,')
        content = content.replace('orm_mode = True', 'from_attributes=True,')
        content = content.replace('extra = "allow"', 'extra="allow",')
        
    if content != orig:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Migrated {cf}')
