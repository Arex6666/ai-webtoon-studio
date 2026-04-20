import glob
import re
import os

files = glob.glob('apps/api/app/**/*.py', recursive=True) + glob.glob('apps/api/tests/**/*.py', recursive=True)

complex_files = [
    'bundle_manifest.py',
    'layerpack_manifest.py',
    'chapter_layout.py',
    'panel_spec.py',
    'assets_lock.py'
]

count = 0
for f in files:
    # Skip complex files for manual editing
    if any(cf in f for cf in complex_files):
        continue
        
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    orig = content
    
    if 'class Config:' in content:
        # Add ConfigDict import
        if 'from pydantic import ' in content and 'ConfigDict' not in content:
            content = content.replace('from pydantic import ', 'from pydantic import ConfigDict, ', 1)
        elif 'from pydantic import' not in content and 'import pydantic' not in content:
            content = 'from pydantic import ConfigDict\n' + content
    
        def repl(m):
            indent = m.group(1)
            body = m.group(2)
            args = []
            
            for line in body.split('\n'):
                line = line.strip()
                if not line or line == 'pass': continue
                if 'orm_mode' in line: args.append('from_attributes=True')
                elif 'populate_by_name' in line: args.append('populate_by_name=True')
                elif 'use_enum_values' in line: args.append('use_enum_values=True')
                elif 'arbitrary_types_allowed' in line: args.append('arbitrary_types_allowed=True')
                elif 'alias_generator' in line: args.append(line)
                elif 'extra' in line: args.append(line)
            
            args_str = ", ".join(args)
            return f'{indent}model_config = ConfigDict({args_str})'
            
        content = re.sub(r'([ \t]*)class Config:\n((?:[ \t]+[^\n]*\n?)+)', repl, content)
        
    if content != orig:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
        count += 1

print(f"Migrated {count} simple Config files.")
