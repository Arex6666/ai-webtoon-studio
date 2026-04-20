import os
import glob
import re

def migrate_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Add ConfigDict import if class Config: is present
    if 'class Config:' in content:
        if 'from pydantic import ' in content and 'ConfigDict' not in content:
            content = content.replace('from pydantic import ', 'from pydantic import ConfigDict, ', 1)
        elif 'from pydantic import' not in content and 'import pydantic' not in content:
            content = 'from pydantic import ConfigDict\n' + content
        elif 'from pydantic import' not in content:
            content = 'from pydantic import ConfigDict\n' + content

        # Replace class Config block
        def repl_config(m):
            indent = m.group(1)
            body = m.group(2)
            args = []
            for line in body.split('\n'):
                line = line.strip()
                if not line or line == 'pass': continue
                if 'orm_mode = True' in line: args.append('from_attributes=True')
                elif 'alias_generator =' in line: args.append(line)
                elif 'populate_by_name = True' in line: args.append('populate_by_name=True')
                elif 'arbitrary_types_allowed = True' in line: args.append('arbitrary_types_allowed=True')
                elif 'allow_population_by_field_name = True' in line: args.append('populate_by_name=True')
                elif 'env_file =' in line: pass # skipped for BaseSettings, requires different config
                else: args.append(line)
            
            args_str = ", ".join(args)
            return f'{indent}model_config = ConfigDict({args_str})'
            
        content = re.sub(r'([ \t]*)class Config:\n((?:[ \t]+.+\n?)+)', repl_config, content)

    # Method rewrites
    content = content.replace('.dict(', '.model_dump(')
    content = content.replace('.parse_obj(', '.model_validate(')
    content = content.replace('.parse_raw(', '.model_validate_json(')
    
    # Write back if changed
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Migrated {filepath}")
        return True
    return False

if __name__ == '__main__':
    files = glob.glob('apps/api/app/**/*.py', recursive=True) + glob.glob('apps/api/tests/**/*.py', recursive=True)
    count = 0
    for f in files:
        if migrate_file(f):
            count += 1
    print(f"Migration completed. Modified {count} files.")
