import sys, re

sys.stdout.reconfigure(encoding='utf-8')

filepath = r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Check section 6.3 code block
code_match = re.search(r'`python\n(.*?)`', content[content.find('### 6.3'):], re.DOTALL)
if code_match:
    code = code_match.group(1)
    # Execute code in sandbox dict
    loc = {}
    exec(code, {}, loc)
    print('Executed 6.3 successfully!')
